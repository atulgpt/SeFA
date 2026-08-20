from sefa.utils import date_utils
from sefa.utils.runtime_utils import warn_missing_module
from sefa.utils import logger
from sefa.utils.excel_utils import (
    cell_text,
    optional_cell_text,
    assert_sheet_names,
    to_float,
)
from sefa.models.transaction import Transaction, Price
from sefa.models.asset_sale import (
    AssetSale,
    NOT_APPLICABLE,
)
from sefa.models.section_type import SectionType
from sefa.models.section_data import SectionDataMap
from sefa.parser.demat.groww.constants import NON_EQUITY_LINKED_SHARES

warn_missing_module("pandas")
warn_missing_module("openpyxl")
import pandas as pd
import typing as t

DEBUG = False

CURRENCY_CODE = "INR"

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
# already applied the listed equity twelve month rule while building the report.
# `<label> -> (equity oriented section, non equity oriented section)`
BLOCK_SECTION_TYPES: t.Dict[str, t.Tuple[SectionType, SectionType]] = {
    SHORT_TERM_BLOCK_LABEL: (SectionType.SECTION_111A, SectionType.SECTION_SLAB_SHORT),
    LONG_TERM_BLOCK_LABEL: (SectionType.SECTION_112A, SectionType.SECTION_SLAB_LONG),
}

# The statement states its charges as one block of `<label>, <amount>` rows sitting
# above the trades. Securities transaction tax is not deductible while computing the
# capital gain, so only the rest of the total is carried into the sales
CHARGES_BLOCK_LABEL = "Charges"
STT_CHARGE_LABEL = "STT"
TOTAL_CHARGE_LABEL = "Total"

NAME_HEADER = "Stock name"
ISIN_HEADER = "ISIN"
QUANTITY_HEADER = "Quantity"
PURCHASE_DATE_HEADER = "Buy date"
PURCHASE_PRICE_HEADER = "Buy price"
SALE_DATE_HEADER = "Sell date"
SALE_PRICE_HEADER = "Sell price"
GAINS_HEADER = "Realised P&L"

REQUIRED_HEADERS = (
    NAME_HEADER,
    ISIN_HEADER,
    QUANTITY_HEADER,
    PURCHASE_DATE_HEADER,
    PURCHASE_PRICE_HEADER,
    SALE_DATE_HEADER,
    SALE_PRICE_HEADER,
    GAINS_HEADER,
)


def __build_column_map(header: pd.Series) -> t.Dict[str, int]:
    column_map: t.Dict[str, int] = {}
    for column_index in range(len(header)):
        name = optional_cell_text(header.iloc[column_index])
        if name != "" and name not in column_map:
            column_map[name] = column_index
    return column_map


def __parse_charges(sheet_pd: pd.DataFrame) -> t.Optional[float]:
    """
    Deductible charges of the whole statement, being its stated total less the
    securities transaction tax. None when the sheet carries no charges block
    """
    label_row_index = None
    for row_index in range(len(sheet_pd)):
        if optional_cell_text(sheet_pd.iloc[row_index].iloc[0]) == CHARGES_BLOCK_LABEL:
            label_row_index = row_index
            break
    if label_row_index is None:
        return None

    charges: t.Dict[str, float] = {}
    for row_index in range(label_row_index + 1, len(sheet_pd)):
        label = optional_cell_text(sheet_pd.iloc[row_index].iloc[0])
        if label == "":
            break
        charges[label] = to_float(sheet_pd.iloc[row_index].iloc[1])

    missing_labels = [
        label
        for label in (STT_CHARGE_LABEL, TOTAL_CHARGE_LABEL)
        if label not in charges
    ]
    assert not missing_labels, (
        f"{CHARGES_BLOCK_LABEL} block is missing the row(s) {missing_labels}."
        + f" Found rows = {sorted(charges)}"
    )
    return round(charges[TOTAL_CHARGE_LABEL] - charges[STT_CHARGE_LABEL], 2)


def __apply_charges(sales: t.List[AssetSale], deductible_charges: float) -> None:
    """
    The statement states its charges only as a whole, so they are split across the
    sales in proportion to their sale value. The last sale absorbs the rounding
    remainder so that the split adds back to the stated amount
    """
    total_sale_value = sum(sale.sale_transaction.total_value() for sale in sales)
    assert total_sale_value > 0, (
        f"Charges of {deductible_charges} cannot be split across sales carrying no"
        " sale value"
    )

    allocated_charges = 0.0
    for index, sale in enumerate(sales):
        if index == len(sales) - 1:
            expense = round(deductible_charges - allocated_charges, 2)
        else:
            expense = round(
                deductible_charges
                * sale.sale_transaction.total_value()
                / total_sale_value,
                2,
            )
            allocated_charges += expense
        sale.expense_original = Price(expense, CURRENCY_CODE)
        sale.expense_exempted = Price(expense, CURRENCY_CODE)
        sale.gains = Price(round(sale.gains.price - expense, 2), CURRENCY_CODE)


def __parse_row(
    data: pd.Series,
    column_map: t.Dict[str, int],
    section_types: t.Tuple[SectionType, SectionType],
) -> AssetSale:
    def cell(header: str) -> t.Any:
        return data.iloc[column_map[header]]

    quantity = to_float(cell(QUANTITY_HEADER))
    name = cell_text(cell(NAME_HEADER))

    equity_section, non_equity_section = section_types
    section_type = (
        non_equity_section if name in NON_EQUITY_LINKED_SHARES else equity_section
    )

    return AssetSale(
        asset_description=name,
        broker=BROKER,
        section_type=section_type,
        sale_transaction=Transaction(
            date=date_utils.parse_dd_mm_yyyy(cell_text(cell(SALE_DATE_HEADER))),
            fmv=Price(to_float(cell(SALE_PRICE_HEADER)), CURRENCY_CODE),
            quantity=quantity,
        ),
        purchase_transaction=Transaction(
            date=date_utils.parse_dd_mm_yyyy(cell_text(cell(PURCHASE_DATE_HEADER))),
            fmv=Price(to_float(cell(PURCHASE_PRICE_HEADER)), CURRENCY_CODE),
            quantity=quantity,
        ),
        # filled once every sale of the statement is known, the charges being split
        # across them in proportion to their sale value
        expense_original=Price(0.0, CURRENCY_CODE),
        expense_exempted=Price(0.0, CURRENCY_CODE),
        gains=Price(round(to_float(cell(GAINS_HEADER)), 2), CURRENCY_CODE),
        sale_exchange_rate=None,
        purchase_exchange_rate=None,
        sale_calc_method=NOT_APPLICABLE,
        purchase_calc_method=NOT_APPLICABLE,
        isin=cell_text(cell(ISIN_HEADER)),
    )


def __parse_block(
    sheet_pd: pd.DataFrame,
    label_row_index: int,
    section_types: t.Tuple[SectionType, SectionType],
    time_bounds_in_ms: t.Optional[date_utils.DateBoundsInMs],
) -> t.List[AssetSale]:
    """
    A block runs from its header row up to the first row that no longer carries a
    stock name, which is either the blank separator row or the next block's label
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
        f"Groww stocks table is missing the column(s) {missing_headers}."
        + f" Found columns = {sorted(column_map)}"
    )

    sales: t.List[AssetSale] = []
    for row_index in range(header_row_index + 1, len(sheet_pd)):
        data = sheet_pd.iloc[row_index]
        name = optional_cell_text(data.iloc[0])
        if name == "" or name in BLOCK_LABELS:
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
) -> t.Tuple[t.List[AssetSale], t.Optional[float]]:
    logger.debug_log(f"Currently parsing {sheet_name} sheet")
    sheet_pd = xl.parse(sheet_name=sheet_name, header=None)

    sales: t.List[AssetSale] = []
    for row_index in range(len(sheet_pd)):
        label = optional_cell_text(sheet_pd.iloc[row_index].iloc[0])
        section_types = BLOCK_SECTION_TYPES.get(label)
        if section_types is None:
            continue
        sales.extend(
            __parse_block(sheet_pd, row_index, section_types, time_bounds_in_ms)
        )
    return sales, __parse_charges(sheet_pd)


def parse(
    input_file_abs_path: str,
    time_bounds_in_ms: t.Optional[date_utils.DateBoundsInMs] = None,
) -> SectionDataMap:
    logger.DEBUG = DEBUG
    sales: t.List[AssetSale] = []
    deductible_charges: t.Optional[float] = None
    with pd.ExcelFile(input_file_abs_path, engine="openpyxl") as xl:
        workbook_sheet_names = assert_sheet_names(xl)
        logger.log(f"Total sheets present {workbook_sheet_names}")
        for sheet_name in workbook_sheet_names:
            sheet_sales, sheet_charges = parse_sheet(xl, sheet_name, time_bounds_in_ms)
            sales.extend(sheet_sales)
            if sheet_charges is not None:
                assert deductible_charges is None, (
                    f"More than one {CHARGES_BLOCK_LABEL} block is present across"
                    f" the sheets {workbook_sheet_names}"
                )
                deductible_charges = sheet_charges

    assert deductible_charges is not None, (
        f"Excel sheet has no {CHARGES_BLOCK_LABEL} block stating the"
        f" {TOTAL_CHARGE_LABEL} and the {STT_CHARGE_LABEL} charges"
    )

    assert sales, (
        "Excel sheet don't have any block matching " + f"{list(BLOCK_SECTION_TYPES)}"
    )

    sales.sort(key=lambda sale: sale.sale_transaction.date["time_in_millis"])
    __apply_charges(sales, deductible_charges)

    print(
        f"Total Indian stock sale entries = {len(sales)}, "
        + f"total gains({CURRENCY_CODE}) = "
        + f"{round(sum(map(lambda sale: sale.gains.price, sales)), 2)}"
    )

    sections: SectionDataMap = SectionDataMap()
    for sale in sales:
        sections.setdefault(sale.section_type, []).append(sale)
    return sections
