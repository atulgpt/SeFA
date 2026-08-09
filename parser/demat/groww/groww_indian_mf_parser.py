from utils.runtime_utils import warn_missing_module
from utils import logger, date_utils
from utils.excel_utils import cell_text, optional_cell_text, to_float
from models.transaction import Transaction, Price
from models.asset_sale import (
    AssetSale,
    NOT_APPLICABLE,
)
from models.section_type import SectionType
from models.section_data import SectionDataMap

warn_missing_module("pandas")
warn_missing_module("openpyxl")
import pandas as pd
import typing as t

DEBUG = False

CURRENCY_CODE = "INR"

BROKER = "Groww"

# The Groww capital gains statement splits the redemptions into one block per asset
# class, each block starting with its label in the first column and followed by its
# own header row. Only an equity oriented fund is eligible for section 111A/112A,
# every other class being reported under the corresponding "other than" section
EQUITY_CATEGORY_LABEL = "Equity Category"
SPECIFIED_DEBT_CATEGORY_LABEL = "Debt (Specified - Other than Equity) Category"
UNSPECIFIED_DEBT_CATEGORY_LABEL = "Debt (Unspecified - Other than Equity) Category"

# `<label> -> (short term section, long term section)`
CATEGORY_SECTION_TYPES: t.Dict[str, t.Tuple[SectionType, SectionType]] = {
    EQUITY_CATEGORY_LABEL: (SectionType.SECTION_111A, SectionType.SECTION_112A),
    SPECIFIED_DEBT_CATEGORY_LABEL: (
        SectionType.SECTION_SLAB_SHORT,
        SectionType.SECTION_SLAB_LONG,
    ),
    UNSPECIFIED_DEBT_CATEGORY_LABEL: (
        SectionType.SECTION_SLAB_SHORT,
        SectionType.SECTION_SLAB_LONG,
    ),
}

NAME_HEADER = "Scheme Name"
PURCHASE_DATE_HEADER = "Purchase Date"
QUANTITY_HEADER = "Matched Quantity"
PURCHASE_PRICE_HEADER = "Purchase Price"
SALE_DATE_HEADER = "Redeem Date"
SALE_PRICE_HEADER = "Redeem Price"
GRANDFATHERED_NAV_HEADER = "Grandfathered Nav"
SHORT_TERM_GAINS_HEADER = "Short Term-Capital Gain"
LONG_TERM_GAINS_HEADER = "Long Term-Capital Gain"

REQUIRED_HEADERS = (
    NAME_HEADER,
    PURCHASE_DATE_HEADER,
    QUANTITY_HEADER,
    PURCHASE_PRICE_HEADER,
    SALE_DATE_HEADER,
    SALE_PRICE_HEADER,
    GRANDFATHERED_NAV_HEADER,
    SHORT_TERM_GAINS_HEADER,
    LONG_TERM_GAINS_HEADER,
)


def __build_column_map(header: pd.Series) -> t.Dict[str, int]:
    column_map: t.Dict[str, int] = {}
    for column_index in range(len(header)):
        name = optional_cell_text(header.iloc[column_index])
        if name != "" and name not in column_map:
            column_map[name] = column_index
    return column_map


def __is_long_term(short_term_gains: float, long_term_gains: float) -> bool:
    """
    Groww states a redemption's gain under the column of its own holding period, so
    the populated column is what classifies the row
    """
    assert (short_term_gains != 0.0) != (long_term_gains != 0.0), (
        "Redemption must state its gain under exactly one of"
        f" {SHORT_TERM_GAINS_HEADER}/{LONG_TERM_GAINS_HEADER}, found"
        f" {short_term_gains}/{long_term_gains}"
    )
    return long_term_gains != 0.0


def __parse_row(
    data: pd.Series,
    column_map: t.Dict[str, int],
    section_types: t.Tuple[SectionType, SectionType],
) -> AssetSale:
    def cell(header: str):
        return data.iloc[column_map[header]]

    quantity = to_float(cell(QUANTITY_HEADER))
    purchase_date = date_utils.parse_yyyy_mm_dd(cell_text(cell(PURCHASE_DATE_HEADER)))
    sale_date = date_utils.parse_yyyy_mm_dd(cell_text(cell(SALE_DATE_HEADER)))
    short_term_gains = to_float(cell(SHORT_TERM_GAINS_HEADER))
    long_term_gains = to_float(cell(LONG_TERM_GAINS_HEADER))

    short_term_section, long_term_section = section_types
    section_type = (
        long_term_section
        if __is_long_term(short_term_gains, long_term_gains)
        else short_term_section
    )

    return AssetSale(
        asset_description=cell_text(cell(NAME_HEADER)),
        broker=BROKER,
        section_type=section_type,
        sale_transaction=Transaction(
            date=sale_date,
            fmv=Price(to_float(cell(SALE_PRICE_HEADER)), CURRENCY_CODE),
            quantity=quantity,
        ),
        purchase_transaction=Transaction(
            date=purchase_date,
            fmv=Price(to_float(cell(PURCHASE_PRICE_HEADER)), CURRENCY_CODE),
            quantity=quantity,
        ),
        # the statement carries no per redemption charge, exit load and stamp duty
        # already being netted off the redeem price
        expense_original=Price(0.0, CURRENCY_CODE),
        expense_exempted=Price(0.0, CURRENCY_CODE),
        # the stated gain already accounts for the grandfathered 31-Jan-2018 NAV,
        # so it is read off the report rather than derived from the two legs
        gains=Price(round(short_term_gains + long_term_gains, 2), CURRENCY_CODE),
        sale_exchange_rate=None,
        purchase_exchange_rate=None,
        sale_calc_method=NOT_APPLICABLE,
        purchase_calc_method=NOT_APPLICABLE,
        fmv_31_jan_2018=Price(to_float(cell(GRANDFATHERED_NAV_HEADER)), CURRENCY_CODE),
    )


def __parse_block(
    sheet_pd: pd.DataFrame,
    label_row_index: int,
    section_types: t.Tuple[SectionType, SectionType],
    time_bounds_in_ms: t.Optional[date_utils.DateBoundsInMs],
) -> t.List[AssetSale]:
    """
    A block runs from its header row up to the first row that no longer carries a
    scheme name, which is either the blank separator row or the next block's label
    """
    header_row_index = None
    for row_index in range(label_row_index + 1, len(sheet_pd)):
        if optional_cell_text(sheet_pd.iloc[row_index].iloc[0]) == NAME_HEADER:
            header_row_index = row_index
            break
    assert header_row_index is not None, (
        f"Block {sheet_pd.iloc[label_row_index].iloc[0]} has no header row starting"
        f" with {NAME_HEADER}"
    )

    column_map = __build_column_map(sheet_pd.iloc[header_row_index])
    missing_headers = [
        header for header in REQUIRED_HEADERS if header not in column_map
    ]
    assert not missing_headers, (
        f"Groww mutual fund table is missing the column(s) {missing_headers}."
        + f" Found columns = {sorted(column_map)}"
    )

    sales: t.List[AssetSale] = []
    for row_index in range(header_row_index + 1, len(sheet_pd)):
        data = sheet_pd.iloc[row_index]
        name = optional_cell_text(data.iloc[0])
        if name == "" or name in CATEGORY_SECTION_TYPES:
            break
        parsed_sale = __parse_row(data, column_map, section_types)
        if not date_utils.is_in_bounds(
            parsed_sale.sale_transaction.date["time_in_millis"], time_bounds_in_ms
        ):
            continue
        sales.append(parsed_sale)
    return sales


def parse_sheet(
    xl: pd.ExcelFile,
    sheet_name: str,
    time_bounds_in_ms: t.Optional[date_utils.DateBoundsInMs],
) -> t.List[AssetSale]:
    logger.debug_log(f"Currently parsing {sheet_name} sheet")
    sheet_pd = xl.parse(sheet_name=sheet_name, header=None)

    sales: t.List[AssetSale] = []
    for row_index in range(len(sheet_pd)):
        label = optional_cell_text(sheet_pd.iloc[row_index].iloc[0])
        section_types = CATEGORY_SECTION_TYPES.get(label)
        if section_types is None:
            continue
        sales.extend(__parse_block(sheet_pd, row_index, section_types, time_bounds_in_ms))
    return sales


def parse(
    input_file_abs_path: str,
    time_bounds_in_ms: t.Optional[date_utils.DateBoundsInMs] = None,
) -> SectionDataMap:
    logger.DEBUG = DEBUG
    sales: t.List[AssetSale] = []
    with pd.ExcelFile(input_file_abs_path, engine="openpyxl") as xl:
        logger.log(f"Total sheets present {xl.sheet_names}")
        for sheet_name in xl.sheet_names:
            sales.extend(parse_sheet(xl, sheet_name, time_bounds_in_ms))

    assert sales, (
        "Excel sheet don't have any block matching " + f"{list(CATEGORY_SECTION_TYPES)}"
    )

    sales.sort(key=lambda sale: sale.sale_transaction.date["time_in_millis"])

    print(
        f"Total Indian mutual fund sale entries = {len(sales)}, "
        + f"total gains({CURRENCY_CODE}) = "
        + f"{round(sum(map(lambda sale: sale.gains.price, sales)), 2)}"
    )

    sections: SectionDataMap = {}
    for sale in sales:
        sections.setdefault(sale.section_type, []).append(sale)
    return sections
