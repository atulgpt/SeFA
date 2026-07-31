from utils.runtime_utils import warn_missing_module
from utils import logger, date_utils
from models.transaction import Transaction, Price
from models.asset_sale import (
    AssetSale,
    NOT_APPLICABLE,
    SECTION_111A,
    SECTION_112A,
    SectionType,
)

warn_missing_module("pandas")
warn_missing_module("openpyxl")
import pandas as pd
import typing as t

DEBUG = False

# Indian listed stocks are traded and reported in INR, so no conversion applies
CURRENCY_CODE = "INR"
REPORTING_CURRENCY_CODE = "INR"

BROKER = "Groww"

# The Groww capital gains statement holds every realized trade on one sheet, split
# into blocks that each start with a label in the first column and are followed by
# their own header row. Only the two capital gain blocks are read: intraday trades
# are speculative business income and buyback proceeds are taxed under section 115QA,
# neither of which belongs in schedule CG
SHORT_TERM_BLOCK_LABEL = "Short Term trades"
LONG_TERM_BLOCK_LABEL = "Long Term trades"
INTRADAY_BLOCK_LABEL = "Intraday trades"
BUYBACK_BLOCK_LABEL = "Buyback trades"
BLOCK_LABELS = (
    SHORT_TERM_BLOCK_LABEL,
    LONG_TERM_BLOCK_LABEL,
    INTRADAY_BLOCK_LABEL,
    BUYBACK_BLOCK_LABEL,
)

# the block a sale is read from is what decides its holding period, Groww having
# already applied the listed equity twelve month rule while building the report
BLOCK_SECTION_TYPES: t.Dict[str, SectionType] = {
    SHORT_TERM_BLOCK_LABEL: SECTION_111A,
    LONG_TERM_BLOCK_LABEL: SECTION_112A,
}

NAME_HEADER = "Stock name"
QUANTITY_HEADER = "Quantity"
PURCHASE_DATE_HEADER = "Buy date"
PURCHASE_PRICE_HEADER = "Buy price"
SALE_DATE_HEADER = "Sell date"
SALE_PRICE_HEADER = "Sell price"
GAINS_HEADER = "Realised P&L"

REQUIRED_HEADERS = (
    NAME_HEADER,
    QUANTITY_HEADER,
    PURCHASE_DATE_HEADER,
    PURCHASE_PRICE_HEADER,
    SALE_DATE_HEADER,
    SALE_PRICE_HEADER,
    GAINS_HEADER,
)


def __cell_text(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def __to_float(value) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0.0
    if isinstance(value, str):
        stripped = value.strip().replace(",", "")
        if stripped == "":
            return 0.0
        return float(stripped)
    return float(value)


def __parse_date(value) -> date_utils.DateObj:
    """
    Trade dates come either as a `DD-MM-YYYY` string or as a datetime when the cell
    is stored as a real date in the workbook
    """
    if isinstance(value, str):
        return date_utils.parse_dd_mm_yyyy(value.strip())
    return date_utils.parse_dd_mm_yyyy(pd.Timestamp(value).strftime("%d-%m-%Y"))


def __build_column_map(header: pd.Series) -> t.Dict[str, int]:
    column_map: t.Dict[str, int] = {}
    for column_index in range(len(header)):
        name = __cell_text(header.iloc[column_index])
        if name != "" and name not in column_map:
            column_map[name] = column_index
    return column_map


def __parse_row(
    data: pd.Series, column_map: t.Dict[str, int], section_type: SectionType
) -> AssetSale:
    def cell(header: str):
        return data.iloc[column_map[header]]

    quantity = __to_float(cell(QUANTITY_HEADER))

    return AssetSale(
        asset_description=__cell_text(cell(NAME_HEADER)),
        broker=BROKER,
        section_type=section_type,
        sale_transaction=Transaction(
            date=__parse_date(cell(SALE_DATE_HEADER)),
            fmv=Price(__to_float(cell(SALE_PRICE_HEADER)), CURRENCY_CODE),
            quantity=quantity,
        ),
        purchase_transaction=Transaction(
            date=__parse_date(cell(PURCHASE_DATE_HEADER)),
            fmv=Price(__to_float(cell(PURCHASE_PRICE_HEADER)), CURRENCY_CODE),
            quantity=quantity,
        ),
        # Groww states the brokerage, STT and statutory charges only as a statement
        # wide summary, so no expense can be attributed to an individual trade
        expense_original=Price(0.0, REPORTING_CURRENCY_CODE),
        expense_exempted=Price(0.0, REPORTING_CURRENCY_CODE),
        gains=Price(
            round(__to_float(cell(GAINS_HEADER)), 2), REPORTING_CURRENCY_CODE
        ),
        sale_exchange_rate=None,
        purchase_exchange_rate=None,
        sale_calc_method=NOT_APPLICABLE,
        purchase_calc_method=NOT_APPLICABLE,
    )


def __parse_block(
    sheet_pd: pd.DataFrame,
    label_row_index: int,
    section_type: SectionType,
    time_bounds: t.Optional[date_utils.DateBounds],
) -> t.List[AssetSale]:
    """
    A block runs from its header row up to the first row that no longer carries a
    stock name, which is either the blank separator row or the next block's label
    """
    header_row_index = None
    for row_index in range(label_row_index + 1, len(sheet_pd)):
        if __cell_text(sheet_pd.iloc[row_index].iloc[0]) == NAME_HEADER:
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
        f"Groww stocks table is missing the column(s) {missing_headers}."
        + f" Found columns = {sorted(column_map)}"
    )

    sales: t.List[AssetSale] = []
    for row_index in range(header_row_index + 1, len(sheet_pd)):
        data = sheet_pd.iloc[row_index]
        name = __cell_text(data.iloc[0])
        if name == "" or name in BLOCK_LABELS:
            break
        parsed_sale = __parse_row(data, column_map, section_type)
        if not date_utils.is_in_bounds(
            parsed_sale.sale_transaction.date["time_in_millis"], time_bounds
        ):
            continue
        sales.append(parsed_sale)
    return sales


def parse_sheet(
    xl: pd.ExcelFile,
    sheet_name: str,
    time_bounds: t.Optional[date_utils.DateBounds],
) -> t.List[AssetSale]:
    logger.debug_log(f"Currently parsing {sheet_name} sheet")
    sheet_pd = xl.parse(sheet_name=sheet_name, header=None)

    sales: t.List[AssetSale] = []
    for row_index in range(len(sheet_pd)):
        label = __cell_text(sheet_pd.iloc[row_index].iloc[0])
        section_type = BLOCK_SECTION_TYPES.get(label)
        if section_type is None:
            continue
        sales.extend(
            __parse_block(sheet_pd, row_index, section_type, time_bounds)
        )
    return sales


def parse(
    input_file_abs_path: str,
    time_bounds: t.Optional[date_utils.DateBounds] = None,
) -> t.List[AssetSale]:
    logger.DEBUG = DEBUG
    sales: t.List[AssetSale] = []
    with pd.ExcelFile(input_file_abs_path, engine="openpyxl") as xl:
        logger.log(f"Total sheets present {xl.sheet_names}")
        for sheet_name in xl.sheet_names:
            sales.extend(parse_sheet(xl, sheet_name, time_bounds))

    if not sales:
        logger.log(
            "Excel sheet don't have any block matching "
            + f"{list(BLOCK_SECTION_TYPES)}"
        )
        return []

    sales.sort(key=lambda sale: sale.sale_transaction.date["time_in_millis"])

    print(
        f"Total Indian stock sale entries = {len(sales)}, "
        + f"total gains({REPORTING_CURRENCY_CODE}) = "
        + f"{round(sum(map(lambda sale: sale.gains.price, sales)), 2)}"
    )
    return sales
