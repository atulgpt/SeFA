import re

from utils.runtime_utils import warn_missing_module
from utils import logger, date_utils
from utils.excel_utils import EMPTY_CELL_MARKER, cell_text, optional_cell_text, to_float
from utils.rates import rbi_rates_utils
from models.transaction import Transaction, Price
from models.asset_sale import (
    AssetSale,
    SBI_PREV_MON_LAST_DAY,
)
from models.section_type import SectionType
from models.section_data import SectionDataMap
from models.itr.faa3 import FAA3
from models.org import Organization

warn_missing_module("pandas")
warn_missing_module("openpyxl")
import pandas as pd
import typing as t

DEBUG = False

# INDmoney consolidated tax report holds the US stock trades under both the short
# term and the long term capital gain sheets. The sheets are matched by pattern so
# that a rename on the INDmoney side (`STCG` -> `Short Term Capital Gains`) keeps
# working. A matched sheet without a US stocks table is skipped while parsing
STCG_SHEET_NAME_PATTERN = re.compile(r"st\s*cg|short[\s\-_]*term", re.IGNORECASE)
LTCG_SHEET_NAME_PATTERN = re.compile(r"lt\s*cg|long[\s\-_]*term", re.IGNORECASE)
SUPPORTED_SHEET_NAME_PATTERNS = (STCG_SHEET_NAME_PATTERN, LTCG_SHEET_NAME_PATTERN)

# US stocks in the INDmoney report are always denominated in US$
CURRENCY_CODE = "USD"
# the report already states the gains in INR, which is also what schedule CG needs
REPORTING_CURRENCY_CODE = "INR"

# the US stock table is the only capital gain table carrying an exchange rate,
# which is what makes these two labels a unique fingerprint for its header row
NAME_HEADER = "Name of Stock"
EXCHANGE_RATE_HEADER = "Exchange Rate"

# `<main header> | <sub header>` keys built out of the two stacked header rows.
# A key is a tuple when the same column is labelled differently across sheets
NAME_KEY = (NAME_HEADER,)
SALE_DATE_KEY = ("Redemption date", "Sell date")
PURCHASE_DATE_KEY = ("Purchase date",)
QUANTITY_KEY = ("Qty sold",)
SALE_VALUE_KEY = ("Total (in US$) | Sell Value",)
PURCHASE_VALUE_KEY = ("Total (in US$) | Purchase Value",)
# the report states the expense in both US$ and INR, the INR one already being
# the US$ one converted, so only the INR figures are read
SALE_EXPENSE_KEY = ("Expense (in INR) | On Sale of Shares",)
PURCHASE_EXPENSE_KEY = ("Expense (in INR) | On Purchase of Shares",)
BROKER_KEY = ("Broker name",)

# Schedule FA section A3 of the same workbook, one row per foreign holding. The
# figures are already stated in INR, so nothing is derived from a ticker
FA_SHEET_NAME_PATTERN = re.compile(r"schedule\s*fa", re.IGNORECASE)
FA_COUNTRY_NAME_HEADER = "Country Name"
FA_COUNTRY_CODE_HEADER = "Country Code"
FA_ENTITY_NAME_HEADER = "Name of the entity"
FA_ADDRESS_HEADER = "Address of the entity"
FA_ZIP_HEADER = "ZIP Code"
FA_NATURE_HEADER = "Nature of entity"
FA_ACQUIRED_DATE_HEADER = "Date of acquiring interest"
FA_INITIAL_VALUE_HEADER = "Initial value of investment"
FA_PEAK_VALUE_HEADER = "Peak value of investment"
FA_CLOSING_VALUE_HEADER = "Closing Balance"
FA_GROSS_PAID_HEADER = "Total gross amount paid/credited to the holding during the period"
FA_GROSS_PROCEEDS_HEADER = (
    "Total gross proceeds from sale or redemption of investment during the period"
)

FA_REQUIRED_HEADERS = (
    FA_COUNTRY_NAME_HEADER,
    FA_COUNTRY_CODE_HEADER,
    FA_ENTITY_NAME_HEADER,
    FA_ADDRESS_HEADER,
    FA_ZIP_HEADER,
    FA_NATURE_HEADER,
    FA_ACQUIRED_DATE_HEADER,
    FA_INITIAL_VALUE_HEADER,
    FA_PEAK_VALUE_HEADER,
    FA_CLOSING_VALUE_HEADER,
    FA_GROSS_PAID_HEADER,
    FA_GROSS_PROCEEDS_HEADER,
)

REQUIRED_KEYS = (
    NAME_KEY,
    SALE_DATE_KEY,
    PURCHASE_DATE_KEY,
    QUANTITY_KEY,
    SALE_VALUE_KEY,
    PURCHASE_VALUE_KEY,
    SALE_EXPENSE_KEY,
    PURCHASE_EXPENSE_KEY,
)

# section markers present in the first data column of the table
GAINS_MARKER = "Gains"
LOSSES_MARKER = "Losses"
TOTAL_MARKER = "Total"


def __parse_date(value) -> date_utils.DateObj:
    """
    Redemption/purchase dates come either as an ISO string or as a datetime when
    the cell is stored as a real date in the workbook
    """
    if isinstance(value, str):
        return date_utils.parse_yyyy_mm_dd(value.strip())
    return date_utils.parse_yyyy_mm_dd(pd.Timestamp(value).strftime("%Y-%m-%d"))


def __find_header_row(sheet_pd: pd.DataFrame) -> t.Optional[int]:
    for row_index in range(len(sheet_pd)):
        row_values = {
            str(value).strip() for value in sheet_pd.iloc[row_index] if pd.notna(value)
        }
        if NAME_HEADER in row_values and EXCHANGE_RATE_HEADER in row_values:
            return row_index
    return None


def __build_column_map(
    main_header: pd.Series, sub_header: pd.Series
) -> t.Dict[str, int]:
    """
    The table has two stacked header rows where a merged main header (for example
    `Total (in US$)`) is split by the sub header row into `Sell Value` and
    `Purchase Value`. Merged cells only carry a value in their first column, so
    the main header is carried forward and joined with the sub header
    """
    column_map: t.Dict[str, int] = {}
    current_main: t.Optional[str] = None
    for column_index in range(len(main_header)):
        main_value = main_header.iloc[column_index]
        if pd.notna(main_value) and str(main_value).strip() != "":
            current_main = str(main_value).strip()
        sub_value = sub_header.iloc[column_index]
        if pd.notna(sub_value) and str(sub_value).strip() != "":
            if current_main is None:
                continue
            key = f"{current_main} | {str(sub_value).strip()}"
        elif pd.notna(main_value) and str(main_value).strip() != "":
            key = current_main
        else:
            continue
        if key not in column_map:
            column_map[key] = column_index
    return column_map


def __is_data_row(name_value) -> bool:
    if not isinstance(name_value, str):
        return False
    name = name_value.strip()
    return name not in ("", GAINS_MARKER, LOSSES_MARKER, EMPTY_CELL_MARKER)


def __column_index(
    column_map: t.Dict[str, int], key: t.Tuple[str, ...]
) -> t.Optional[int]:
    for alias in key:
        if alias in column_map:
            return column_map[alias]
    return None


def __per_unit(total: float, quantity: float) -> float:
    """
    Per unit value is derived from the total rather than read off the report's own
    per unit column, which is rounded and does not always multiply back to the total
    """
    if quantity == 0:
        return 0.0
    return total / quantity


def __section_type(sheet_name: str) -> SectionType:
    """
    US listed shares are not eligible for section 111A/112A, so a sheet only
    decides whether the sale is reported as short term or as long term
    """
    if STCG_SHEET_NAME_PATTERN.search(sheet_name):
        return SectionType.SECTION_SLAB_SHORT
    return SectionType.SECTION_SLAB_LONG


def __parse_row(
    data: pd.Series, column_map: t.Dict[str, int], section_type: SectionType
) -> AssetSale:
    def cell(key: t.Tuple[str, ...]):
        column_index = __column_index(column_map, key)
        if column_index is None:
            return None
        return data.iloc[column_index]

    sale_date = __parse_date(cell(SALE_DATE_KEY))
    purchase_date = __parse_date(cell(PURCHASE_DATE_KEY))
    quantity = to_float(cell(QUANTITY_KEY))

    # Rule 115 converts the capital gain as a whole, so the rate of the transfer
    # month is applied to the purchase leg as well and no purchase rate is looked up
    sale_rate = rbi_rates_utils.get_rate_for_prev_mon_for_time_in_ms(
        CURRENCY_CODE, sale_date["time_in_millis"]
    )

    sale_value = to_float(cell(SALE_VALUE_KEY))
    purchase_value = to_float(cell(PURCHASE_VALUE_KEY))
    sale_price = sale_value * sale_rate
    purchase_price = purchase_value * sale_rate
    expense_exempted = to_float(cell(SALE_EXPENSE_KEY)) + to_float(
        cell(PURCHASE_EXPENSE_KEY)
    )

    return AssetSale(
        asset_description=str(cell(NAME_KEY)).strip(),
        broker=str(cell(BROKER_KEY)).strip() if cell(BROKER_KEY) is not None else "",
        section_type=section_type,
        sale_transaction=Transaction(
            date=sale_date,
            fmv=Price(__per_unit(sale_value, quantity), CURRENCY_CODE),
            quantity=quantity,
        ),
        purchase_transaction=Transaction(
            date=purchase_date,
            fmv=Price(__per_unit(purchase_value, quantity), CURRENCY_CODE),
            quantity=quantity,
        ),
        # both expense_original and expense_exempted is same in case of INDMoney
        expense_original=Price(round(expense_exempted, 2), REPORTING_CURRENCY_CODE),
        expense_exempted=Price(round(expense_exempted, 2), REPORTING_CURRENCY_CODE),
        gains=Price(
            round(sale_price - purchase_price - expense_exempted, 2),
            REPORTING_CURRENCY_CODE,
        ),
        sale_exchange_rate=sale_rate,
        purchase_exchange_rate=None,
        sale_calc_method=SBI_PREV_MON_LAST_DAY,
        purchase_calc_method=SBI_PREV_MON_LAST_DAY,
    )


def parse_sheet(
    xl: pd.ExcelFile,
    sheet_name: str,
    time_bounds: t.Optional[date_utils.DateBounds],
) -> t.List[AssetSale]:
    logger.debug_log(f"Currently parsing {sheet_name} sheet")
    sheet_pd = xl.parse(sheet_name=sheet_name, header=None)

    header_row_index = __find_header_row(sheet_pd)
    if header_row_index is None:
        logger.log(f"Sheet {sheet_name} has no US stocks table, skipping it")
        return []

    column_map = __build_column_map(
        sheet_pd.iloc[header_row_index], sheet_pd.iloc[header_row_index + 1]
    )
    missing_keys = [
        key for key in REQUIRED_KEYS if __column_index(column_map, key) is None
    ]
    assert not missing_keys, (
        f"US stocks table in {sheet_name} sheet is missing the column(s) {missing_keys}."
        + f" Found columns = {sorted(column_map)}"
    )

    name_column = __column_index(column_map, NAME_KEY)
    assert name_column is not None
    section_type = __section_type(sheet_name)
    sales: t.List[AssetSale] = []
    for row_index in range(header_row_index + 2, len(sheet_pd)):
        data = sheet_pd.iloc[row_index]
        name_value = data.iloc[name_column]
        if isinstance(name_value, str) and name_value.strip() == TOTAL_MARKER:
            break
        if not __is_data_row(name_value):
            continue
        parsed_sale = __parse_row(data, column_map, section_type)
        if not date_utils.is_in_bounds(
            parsed_sale.sale_transaction.date["time_in_millis"], time_bounds
        ):
            continue
        sales.append(parsed_sale)
    return sales


def __parse_fa_sheet(xl: pd.ExcelFile, sheet_name: str) -> t.List[FAA3]:
    """
    Section A3 of the schedule FA sheet, whose header row is the one carrying the
    entity name. The rows above it hold section A2, the foreign custodial accounts,
    which schedule FA under section A3 does not consume
    """
    logger.debug_log(f"Currently parsing {sheet_name} sheet")
    sheet_pd = xl.parse(sheet_name=sheet_name, header=None)

    header_row_index = None
    for row_index in range(len(sheet_pd)):
        row = {
            optional_cell_text(value): index
            for index, value in enumerate(sheet_pd.iloc[row_index])
        }
        if FA_ENTITY_NAME_HEADER in row and FA_ACQUIRED_DATE_HEADER in row:
            header_row_index = row_index
            column_map = row
            break
    assert header_row_index is not None, (
        f"{sheet_name} sheet has no section A3 header row carrying"
        f" {FA_ENTITY_NAME_HEADER} and {FA_ACQUIRED_DATE_HEADER}"
    )

    missing_headers = [
        header for header in FA_REQUIRED_HEADERS if header not in column_map
    ]
    assert not missing_headers, (
        f"Section A3 of {sheet_name} sheet is missing the column(s)"
        f" {missing_headers}. Found columns = {sorted(column_map)}"
    )

    entries: t.List[FAA3] = []
    for row_index in range(header_row_index + 1, len(sheet_pd)):
        data = sheet_pd.iloc[row_index]

        def cell(header: str):
            return data.iloc[column_map[header]]

        if optional_cell_text(cell(FA_ENTITY_NAME_HEADER)) == "":
            break
        entries.append(
            FAA3(
                org=Organization(
                    country_name=cell_text(cell(FA_COUNTRY_NAME_HEADER)),
                    # the report zero pads the code, the utility does not take it
                    country_code=str(int(to_float(cell(FA_COUNTRY_CODE_HEADER)))),
                    name=cell_text(cell(FA_ENTITY_NAME_HEADER)),
                    address=cell_text(cell(FA_ADDRESS_HEADER)),
                    nature=cell_text(cell(FA_NATURE_HEADER)),
                    zip_code=cell_text(cell(FA_ZIP_HEADER)),
                ),
                purchase_date=date_utils.parse_yyyy_mm_dd(
                    cell_text(cell(FA_ACQUIRED_DATE_HEADER))
                ),
                purchase_price=to_float(cell(FA_INITIAL_VALUE_HEADER)),
                peak_price=to_float(cell(FA_PEAK_VALUE_HEADER)),
                closing_price=to_float(cell(FA_CLOSING_VALUE_HEADER)),
                gross_amount_paid=to_float(cell(FA_GROSS_PAID_HEADER)),
                gross_sale_proceeds=to_float(cell(FA_GROSS_PROCEEDS_HEADER)),
            )
        )
    return entries


def parse(
    input_file_abs_path: str,
    time_bounds: t.Optional[date_utils.DateBounds] = None,
) -> SectionDataMap:
    logger.DEBUG = DEBUG
    sales: t.List[AssetSale] = []
    fa_entries: t.List[FAA3] = []
    with pd.ExcelFile(input_file_abs_path, engine="openpyxl") as xl:
        sheet_names = xl.sheet_names
        logger.log(f"Total sheets present {sheet_names}")
        # dict keys keep the short term before long term ordering while dropping a
        # sheet that happens to match both patterns from being parsed twice
        parsable_sheet_names = list(
            dict.fromkeys(
                sheet_name
                for pattern in SUPPORTED_SHEET_NAME_PATTERNS
                for sheet_name in sheet_names
                if pattern.search(sheet_name)
            )
        )
        assert parsable_sheet_names, (
            "Excel sheet don't have any sheet matching "
            + f"{[pattern.pattern for pattern in SUPPORTED_SHEET_NAME_PATTERNS]}"
        )
        for sheet_name in parsable_sheet_names:
            sales.extend(parse_sheet(xl, sheet_name, time_bounds))

        for sheet_name in sheet_names:
            if FA_SHEET_NAME_PATTERN.search(sheet_name):
                fa_entries.extend(__parse_fa_sheet(xl, sheet_name))

    sales.sort(key=lambda sale: sale.sale_transaction.date["time_in_millis"])

    print(
        f"Total US stock sale entries = {len(sales)}, "
        + f"total gains({REPORTING_CURRENCY_CODE}) = "
        + f"{round(sum(map(lambda sale: sale.gains.price, sales)), 2)}"
        + f", schedule FA entries = {len(fa_entries)}"
    )

    sections: SectionDataMap = {}
    for sale in sales:
        sections.setdefault(sale.section_type, []).append(sale)
    if fa_entries:
        sections[SectionType.SCHEDULE_FA_A3] = fa_entries
    return sections
