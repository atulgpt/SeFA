import math

from utils.excel_utils import (
    MONEY_COLUMN_TYPE,
    PLAIN_COLUMN_TYPE,
    REPORTING_COLUMN_TYPE,
    Column,
    currency_column_name,
    header_names,
)
from utils.runtime_utils import warn_missing_module
from utils import logger, file_utils, date_utils
from utils.rates import rbi_rates_utils
from models.transaction import Transaction
from models.asset_sale import AssetSale, SECTION_112A, SECTION_TYPES, SectionType

warn_missing_module("pandas")
warn_missing_module("openpyxl")
import typing as t

DEBUG = False

OUTPUT_FILE_NAME = "asset_sales.xlsx"

SUMMARY_OUTPUT_FILE_NAME = "capital_gain_summary.xlsx"
SUMMARY_OUTPUT_SHEET_NAME = "Capital Gain Summary"
SECTION_COLUMN = "Section"

# The quarter wise accrual of the gain that schedule CG asks for
TOTAL_COLUMN = "Total"
FINANCIAL_YEAR_FIRST_MONTH = 4

# `<label>, <closing (month, day) of the quarter>`
QUARTERS = (
    ("Upto 15/6 (i)", (6, 15)),
    ("16/6 to 15/9 (ii)", (9, 15)),
    ("16/9 to 15/12 (iii)", (12, 15)),
    ("16/12 to 15/3 (iv)", (3, 15)),
    ("16/3 to 31/3 (v)", (3, 31)),
)

SCHEDULE_112A_OUTPUT_FILE_NAME = "schedule_112a.csv"

# only used to label the reporting currency columns of an empty report
DEFAULT_REPORTING_CURRENCY_CODE = "INR"

# printed wherever the source does not apply an exchange rate to a leg
UNUSED_VALUE_MARKER = "-"


# renaming a column here is enough, the row builder looks every value up through
# these same names
SERIAL_NUMBER_COLUMN = "S.No."
ASSET_DESCRIPTION_COLUMN = "Asset Description"
BROKER_COLUMN = "Broker"
SALE_DATE_COLUMN = "Sale Date"
PURCHASE_DATE_COLUMN = "Purchase Date"
SALE_PRICE_COLUMN = "Sale Price"
PURCHASE_PRICE_COLUMN = "Purchase Price"
EXPENSE_COLUMN = "Expense"
GAINS_COLUMN = "Gains(minus expense)"
UNITS_COLUMN = "Units"
SALE_EXCHANGE_RATE_COLUMN = "Exchange Rate(Sale)"
SALE_CALC_METHOD_COLUMN = "Sale Calc Method"
PURCHASE_EXCHANGE_RATE_COLUMN = "Exchange Rate(Purchase)"
PURCHASE_CALC_METHOD_COLUMN = "Purchase Calc Method"

RAW_SHEET_COLUMNS = [
    Column(PLAIN_COLUMN_TYPE, SERIAL_NUMBER_COLUMN),
    Column(PLAIN_COLUMN_TYPE, ASSET_DESCRIPTION_COLUMN),
    Column(PLAIN_COLUMN_TYPE, BROKER_COLUMN),
    Column(PLAIN_COLUMN_TYPE, SALE_DATE_COLUMN),
    Column(PLAIN_COLUMN_TYPE, PURCHASE_DATE_COLUMN),
    Column(MONEY_COLUMN_TYPE, SALE_PRICE_COLUMN),
    Column(MONEY_COLUMN_TYPE, PURCHASE_PRICE_COLUMN),
    Column(REPORTING_COLUMN_TYPE, EXPENSE_COLUMN),
    Column(REPORTING_COLUMN_TYPE, GAINS_COLUMN),
    Column(PLAIN_COLUMN_TYPE, UNITS_COLUMN),
    Column(PLAIN_COLUMN_TYPE, SALE_EXCHANGE_RATE_COLUMN),
    Column(PLAIN_COLUMN_TYPE, SALE_CALC_METHOD_COLUMN),
    Column(PLAIN_COLUMN_TYPE, PURCHASE_EXCHANGE_RATE_COLUMN),
    Column(PLAIN_COLUMN_TYPE, PURCHASE_CALC_METHOD_COLUMN),
]

# schedule CG figures printed under the table, each sitting in the column it totals
FULL_VALUE_OF_CONSIDERATION_LABEL = "Full value of consideration"
COST_OF_ACQUISITION_LABEL = "Cost of acquisition without indexation"
TRANSFER_EXPENDITURE_LABEL = (
    "Expenditure wholly and exclusively in connection with transfer"
)

# `<label>, <column totalled>`, every total being stated in whole rupees
SUMMARY_COLUMNS = (
    (FULL_VALUE_OF_CONSIDERATION_LABEL, SALE_PRICE_COLUMN),
    (COST_OF_ACQUISITION_LABEL, PURCHASE_PRICE_COLUMN),
    (TRANSFER_EXPENDITURE_LABEL, EXPENSE_COLUMN),
)

# Schedule 112A of the ITR, its column headers spelled exactly as the filing utility
# expects them. The trailing empty header is part of the utility's own template
SCHEDULE_112A_COLUMNS = [
    "Share/Unit acquired (On or before / after 31st Jan 2018)(1a)",
    "ISIN Code(2)",
    "Name of the Share/Unit(3)",
    "No. of Shares/Units(4)",
    "Sale-price per Share/Unit(5)",
    "Full Value of Consideration If shares/units are acquired on or before 31st"
    " January, 2018 (Total Sale Value) (4*5) or  If  shares/units are acquired after"
    " 31st January, 2018 - Please enter Full Value of Consideration (6) = 4 * 5",
    "Cost of acquisition without indexation (higher of 8 or 9)(7)",
    "Cost of acquisition(8)",
    "If the long term capital asset was acquired before 01.02.2018, Lower of 6 &"
    " 11(9)",
    "Fair Market Value per share/unit as on 31st January,2018(10)",
    "Total Fair Market Value as on 31st January, 2018 of capital asset as per section"
    " 55(2)(ac)- (4*10)(11)",
    "Expenditure wholly and exclusively in connection with transfer(12)",
    "Total deductions(13) = 7 + 12",
    "Balance(14) = 6 - 13",
    "",
]

# Only a holding acquired on or before this date is reported through the schedule,
# its cost being grandfathered to the 31-Jan-2018 fair market value under section
# 55(2)(ac). A later one carries no grandfathering and is filed as an aggregate
GRANDFATHERING_CUTOFF_DATE = "2018-01-31"
GRANDFATHERING_CUTOFF_IN_MS = date_utils.parse_yyyy_mm_dd(
    GRANDFATHERING_CUTOFF_DATE
)["time_in_millis"]
ACQUIRED_ON_OR_BEFORE_CUTOFF_MARKER = "On or before"


def __exchange_rate(sale: AssetSale, transaction: Transaction) -> float:
    """
    Rule 115 applies the transfer month's rate to the whole computation, so a leg
    without its own rate falls back to the sale leg's one. A leg already traded in
    the reporting currency needs no conversion
    """
    if sale.sale_exchange_rate is not None:
        return sale.sale_exchange_rate
    if transaction.fmv.currency_code == sale.gains.currency_code:
        return 1.0
    return rbi_rates_utils.get_rate_for_prev_mon_for_time_in_ms(
        transaction.fmv.currency_code, transaction.date["time_in_millis"]
    )


def __original_value(transaction: Transaction) -> float:
    return round(transaction.fmv.price * transaction.quantity, 2)


def __reporting_currency_code(sales: t.List[AssetSale]) -> str:
    codes = {sale.gains.currency_code for sale in sales}
    assert len(codes) <= 1, f"Sales report gains in more than one currency: {codes}"
    return codes.pop() if codes else DEFAULT_REPORTING_CURRENCY_CODE


def __currency_codes(sales: t.List[AssetSale], reporting_code: str) -> t.List[str]:
    """
    Traded currencies present in the report, the reporting currency last so that
    its columns always sit after the traded currency ones
    """
    codes = {sale.sale_transaction.fmv.currency_code for sale in sales}
    codes.discard(reporting_code)
    return sorted(codes) + [reporting_code]


def __serial_order_key(sale: AssetSale) -> t.Tuple[str, int]:
    """
    Serial numbers run broker wise and, within a broker, purchase date wise
    """
    return (
        sale.broker.casefold(),
        sale.purchase_transaction.date["time_in_millis"],
    )


def __build_row(
    serial_number: int, sale: AssetSale, columns: t.List[str]
) -> t.Tuple[t.Any, ...]:
    """
    Only the money column set of the sale's own currency is filled, the other
    currency sets stay empty for this row
    """
    reporting_code = sale.gains.currency_code
    original_code = sale.sale_transaction.fmv.currency_code
    original_sale_value = __original_value(sale.sale_transaction)
    original_purchase_value = __original_value(sale.purchase_transaction)
    # a sale traded in the reporting currency has both column sets land on the same
    # name, so the reporting entries are written last and win the collision
    values: t.Dict[str, t.Any] = {
        SERIAL_NUMBER_COLUMN: serial_number,
        ASSET_DESCRIPTION_COLUMN: sale.asset_description,
        BROKER_COLUMN: sale.broker,
        SALE_DATE_COLUMN: sale.sale_transaction.date["disp_time"],
        PURCHASE_DATE_COLUMN: sale.purchase_transaction.date["disp_time"],
        UNITS_COLUMN: sale.sale_transaction.quantity,
        SALE_EXCHANGE_RATE_COLUMN: (
            sale.sale_exchange_rate
            if sale.sale_exchange_rate is not None
            else UNUSED_VALUE_MARKER
        ),
        PURCHASE_EXCHANGE_RATE_COLUMN: (
            sale.purchase_exchange_rate
            if sale.purchase_exchange_rate is not None
            else UNUSED_VALUE_MARKER
        ),
        SALE_CALC_METHOD_COLUMN: sale.sale_calc_method,
        PURCHASE_CALC_METHOD_COLUMN: sale.purchase_calc_method,
        currency_column_name(
            EXPENSE_COLUMN, reporting_code
        ): sale.expense_exempted.price,
        currency_column_name(GAINS_COLUMN, reporting_code): sale.gains.price,
        currency_column_name(SALE_PRICE_COLUMN, original_code): original_sale_value,
        currency_column_name(
            PURCHASE_PRICE_COLUMN, original_code
        ): original_purchase_value,
        currency_column_name(SALE_PRICE_COLUMN, reporting_code): round(
            original_sale_value * __exchange_rate(sale, sale.sale_transaction), 2
        ),
        currency_column_name(PURCHASE_PRICE_COLUMN, reporting_code): round(
            original_purchase_value
            * __exchange_rate(sale, sale.purchase_transaction),
            2,
        ),
    }

    return tuple(values.get(column) for column in columns)


def __whole_rupees(value: float) -> int:
    return math.floor(value + 0.5)


def __section_totals(
    rows: t.List[t.Tuple[t.Any, ...]],
    columns: t.List[str],
    reporting_code: str,
) -> t.Dict[str, int]:
    """
    Schedule CG totals of one section in whole rupees. A total is summed off the
    built rows rather than off the sales so that it always adds back to the figures
    the sheet itself prints
    """
    totals: t.Dict[str, int] = {}
    for label, column in SUMMARY_COLUMNS:
        column_index = columns.index(currency_column_name(column, reporting_code))
        totals[label] = __whole_rupees(
            sum(row[column_index] or 0.0 for row in rows)
        )
    return totals


def __build_summary_rows(
    totals: t.Dict[str, int],
    columns: t.List[str],
    reporting_code: str,
) -> t.List[t.Tuple[t.Any, ...]]:
    """
    Totals of the sheet, separated from the table by a blank row and each sitting in
    the column it totals
    """
    summary_rows: t.List[t.Tuple[t.Any, ...]] = [tuple(None for _ in columns)]
    for label, column in SUMMARY_COLUMNS:
        values: t.List[t.Any] = [None] * len(columns)
        values[0] = label
        values[columns.index(currency_column_name(column, reporting_code))] = totals[
            label
        ]
        summary_rows.append(tuple(values))
    return summary_rows


def __build_sheet(
    section_type: SectionType, sales: t.List[AssetSale]
) -> t.Tuple[
    t.Tuple[str, t.List[str], t.List[t.Tuple[t.Any, ...]]], t.Dict[str, int]
]:
    """
    A sheet holds the sales of one schedule CG section, its columns covering only
    the currencies that section's sales are traded in. Returned alongside the
    section's schedule CG totals
    """
    reporting_currency_code = __reporting_currency_code(sales)
    columns = header_names(
        RAW_SHEET_COLUMNS,
        __currency_codes(sales, reporting_currency_code),
        reporting_currency_code,
    )

    print(
        f"Total {section_type} asset sale entries = {len(sales)}, "
        + f"total gains({reporting_currency_code}) = "
        + f"{round(sum(map(lambda sale: sale.gains.price, sales)), 2)}"
    )

    rows = [
        __build_row(serial_number, sale, columns)
        for serial_number, sale in enumerate(sales, start=1)
    ]
    totals = __section_totals(rows, columns, reporting_currency_code)
    return (
        (
            section_type,
            columns,
            rows
            + __build_summary_rows(totals, columns, reporting_currency_code),
        ),
        totals,
    )


def __financial_year_key(month: int, day: int) -> t.Tuple[int, int]:
    """
    Orders a `(month, day)` inside the financial year, which opens in April
    """
    return (
        (month - FINANCIAL_YEAR_FIRST_MONTH) % 12,
        day,
    )


def __quarter_index(sale: AssetSale) -> int:
    month, day = (
        int(part)
        for part in date_utils.format_time(
            sale.sale_transaction.date["time_in_millis"], "%m-%d"
        ).split("-")
    )
    sale_key = __financial_year_key(month, day)
    for index, (_, (last_month, last_day)) in enumerate(QUARTERS):
        if sale_key <= __financial_year_key(last_month, last_day):
            return index
    return len(QUARTERS) - 1


def __non_negative_quarter_gains(rounded_gains: t.List[int]) -> t.List[int]:
    """
    Schedule CG does not take a negative quarter, so a quarter running at a loss is
    set off against the quarters that follow it and, having none left to follow it,
    against the ones before it. The section total is what is preserved
    """
    gains = list(rounded_gains)
    for index in range(len(gains) - 1):
        if gains[index] < 0:
            gains[index + 1] += gains[index]
            gains[index] = 0
    for index in range(len(gains) - 1, 0, -1):
        if gains[index] < 0:
            gains[index - 1] += gains[index]
            gains[index] = 0
    return gains


def __build_quarter_sheet(
    section_type: SectionType, sales: t.List[AssetSale]
) -> t.Optional[t.Tuple[str, t.List[str], t.List[t.Tuple[t.Any, ...]]]]:
    """
    Quarter wise accrual of the section's gain in whole rupees, one quarter per
    column. Rounding every quarter on its own leaves the parts a rupee or two off the
    section total, so the difference is carried by the last quarter that holds a
    sale. None when the section as a whole runs at a loss, which schedule CG does not
    break up quarter wise
    """
    quarter_gains = [0.0] * len(QUARTERS)
    quarter_holds_sale = [False] * len(QUARTERS)
    for sale in sales:
        quarter_index = __quarter_index(sale)
        quarter_gains[quarter_index] += sale.gains.price
        quarter_holds_sale[quarter_index] = True

    section_total = __whole_rupees(sum(sale.gains.price for sale in sales))
    if section_total < 0:
        logger.log(
            f"Section {section_type} runs at an overall loss of {section_total},"
            " skipping its quarter wise breakup"
        )
        return None

    rounded_gains = [__whole_rupees(gain) for gain in quarter_gains]
    last_quarter_index = max(
        index for index, holds_sale in enumerate(quarter_holds_sale) if holds_sale
    )
    rounded_gains[last_quarter_index] += section_total - sum(rounded_gains)
    rounded_gains = __non_negative_quarter_gains(rounded_gains)
    assert all(
        gain >= 0 for gain in rounded_gains
    ), f"Section {section_type} still holds a negative quarter: {rounded_gains}"

    return (
        section_type,
        [SECTION_COLUMN] + [label for label, _ in QUARTERS] + [TOTAL_COLUMN],
        [(section_type,) + tuple(rounded_gains) + (section_total,)],
    )


def __write_summary(
    output_folder_abs_path: str,
    section_types: t.List[SectionType],
    section_sales: t.Dict[str, t.List[AssetSale]],
    section_totals: t.Dict[str, t.Dict[str, int]],
) -> None:
    """
    The figures that go on the return: one row per schedule CG section, then a sheet
    per section breaking its gain up quarter wise
    """
    columns = [SECTION_COLUMN] + [label for label, _ in SUMMARY_COLUMNS]
    file_utils.write_excel_sheets_to_file(
        output_folder_abs_path,
        SUMMARY_OUTPUT_FILE_NAME,
        [
            (
                SUMMARY_OUTPUT_SHEET_NAME,
                columns,
                [
                    (section_type,)
                    + tuple(
                        section_totals[section_type][label]
                        for label, _ in SUMMARY_COLUMNS
                    )
                    for section_type in section_types
                ],
            )
        ]
        + [
            quarter_sheet
            for quarter_sheet in (
                __build_quarter_sheet(section_type, section_sales[section_type])
                for section_type in section_types
            )
            if quarter_sheet is not None
        ],
        True,
        print_path_to_console=True,
    )


def __schedule_112a_row(sale: AssetSale) -> t.Tuple[t.Any, ...]:
    purchase_transaction = sale.purchase_transaction
    sale_transaction = sale.sale_transaction
    assert sale.isin is not None and sale.isin != "", (
        f"{sale.asset_description} was acquired on"
        f" {purchase_transaction.date['disp_time']} and needs its ISIN, which its"
        " source report does not state"
    )
    assert sale.fmv_31_jan_2018 is not None, (
        f"{sale.asset_description} was acquired on"
        f" {purchase_transaction.date['disp_time']} and is grandfathered under"
        " section 55(2)(ac), which needs the 31-Jan-2018 fair market value its"
        " source report does not state"
    )

    quantity = sale_transaction.quantity
    # the utility rejects a fractional full value of consideration
    consideration = __whole_rupees(sale_transaction.fmv.price * quantity)
    cost = round(purchase_transaction.fmv.price * quantity, 2)
    fmv_total = round(sale.fmv_31_jan_2018.price * quantity, 2)
    grandfathered_cost = min(consideration, fmv_total)
    cost_without_indexation = max(cost, grandfathered_cost)
    expenditure = round(sale.expense_exempted.price, 2)
    deductions = round(cost_without_indexation + expenditure, 2)

    return (
        ACQUIRED_ON_OR_BEFORE_CUTOFF_MARKER,
        sale.isin,
        sale.asset_description,
        quantity,
        sale_transaction.fmv.price,
        consideration,
        cost_without_indexation,
        cost,
        grandfathered_cost,
        sale.fmv_31_jan_2018.price,
        fmv_total,
        expenditure,
        deductions,
        round(consideration - deductions, 2),
        "",
    )


def __write_schedule_112a(
    output_folder_abs_path: str, sales: t.List[AssetSale]
) -> None:
    file_utils.write_csv_to_file(
        output_folder_abs_path,
        SCHEDULE_112A_OUTPUT_FILE_NAME,
        SCHEDULE_112A_COLUMNS,
        [__schedule_112a_row(sale) for sale in sales],
        True,
        print_path_to_console=True,
    )


def parse(
    sales: t.List[AssetSale],
    output_folder_abs_path: str,
) -> t.List[AssetSale]:
    logger.DEBUG = DEBUG
    ordered_sales = sorted(sales, key=__serial_order_key)

    # a sale is reported under exactly one schedule CG section, so every section
    # present gets its own sheet inside the one workbook
    present_section_types = {sale.section_type for sale in ordered_sales}
    section_types = [
        section_type
        for section_type in SECTION_TYPES
        if section_type in present_section_types
    ]

    sheets: t.List[t.Tuple[str, t.List[str], t.List[t.Tuple[t.Any, ...]]]] = []
    section_sales: t.Dict[str, t.List[AssetSale]] = {}
    section_totals: t.Dict[str, t.Dict[str, int]] = {}
    for section_type in section_types:
        section_sales[section_type] = [
            sale for sale in ordered_sales if sale.section_type == section_type
        ]
        sheet, totals = __build_sheet(
            section_type, section_sales[section_type]
        )
        sheets.append(sheet)
        section_totals[section_type] = totals

    file_utils.write_excel_sheets_to_file(
        output_folder_abs_path,
        OUTPUT_FILE_NAME,
        sheets,
        True,
        is_raw=True,
        print_path_to_console=True,
    )

    __write_summary(
        output_folder_abs_path, section_types, section_sales, section_totals
    )

    # only a grandfathered holding goes through the schedule, a later one being
    # filed as an aggregate instead
    schedule_112a_sales = [
        sale
        for sale in ordered_sales
        if sale.section_type == SECTION_112A
        and sale.purchase_transaction.date["time_in_millis"]
        <= GRANDFATHERING_CUTOFF_IN_MS
    ]
    if schedule_112a_sales:
        __write_schedule_112a(output_folder_abs_path, schedule_112a_sales)
    else:
        logger.log(
            f"No {SECTION_112A} sale was acquired on or before"
            f" {GRANDFATHERING_CUTOFF_DATE}, skipping"
            f" {SCHEDULE_112A_OUTPUT_FILE_NAME}"
        )

    return ordered_sales
