from utils.excel_utils import (
    MONEY_COLUMN_TYPE,
    PLAIN_COLUMN_TYPE,
    REPORTING_COLUMN_TYPE,
    Column,
    currency_column_name,
    header_names,
)
from utils.runtime_utils import warn_missing_module
from utils import logger, file_utils
from utils.rates import rbi_rates_utils
from models.transaction import Transaction
from models.asset_sale import AssetSale, SectionType

warn_missing_module("pandas")
warn_missing_module("openpyxl")
import typing as t

DEBUG = False

# one report per schedule CG section, both the file and the sheet carrying the
# section the sales inside it are reported under
OUTPUT_FILE_NAME_FORMAT = "asset_sales.xlsx"

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

COLUMNS = [
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


def __section_type(sales: t.List[AssetSale]) -> SectionType:
    """
    A report covers exactly one schedule CG section, so the caller splits the
    sales by section before handing them over
    """
    section_types = {sale.section_type for sale in sales}
    assert (
        len(section_types) == 1
    ), f"Sales must belong to exactly one section, found {sorted(section_types)}"
    return section_types.pop()


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
    }

    values.update(
        {
            currency_column_name(SALE_PRICE_COLUMN, original_code): __original_value(
                sale.sale_transaction
            ),
            currency_column_name(
                PURCHASE_PRICE_COLUMN, original_code
            ): __original_value(sale.purchase_transaction),
        }
    )

    values.update(
        {
            currency_column_name(SALE_PRICE_COLUMN, reporting_code): round(
                __original_value(sale.sale_transaction)
                * __exchange_rate(sale, sale.sale_transaction),
                2,
            ),
            currency_column_name(PURCHASE_PRICE_COLUMN, reporting_code): round(
                __original_value(sale.purchase_transaction)
                * __exchange_rate(sale, sale.purchase_transaction),
                2,
            ),
        }
    )

    return tuple(values.get(column) for column in columns)


def parse(
    sales: t.List[AssetSale],
    output_folder_abs_path: str,
) -> t.List[AssetSale]:
    logger.DEBUG = DEBUG
    ordered_sales = sorted(sales, key=__serial_order_key)

    section_type = __section_type(ordered_sales)
    reporting_currency_code = __reporting_currency_code(ordered_sales)
    columns = header_names(
        COLUMNS,
        __currency_codes(ordered_sales, reporting_currency_code),
        reporting_currency_code,
    )

    file_utils.write_excel_to_file(
        output_folder_abs_path,
        OUTPUT_FILE_NAME_FORMAT.format(section_type=section_type),
        columns,
        (
            __build_row(serial_number, sale, columns)
            for serial_number, sale in enumerate(ordered_sales, start=1)
        ),
        True,
        sheet_name=section_type,
        print_path_to_console=True,
    )

    print(
        f"Total {section_type} asset sale entries = {len(ordered_sales)}, "
        + f"total gains({reporting_currency_code}) = "
        + f"{round(sum(map(lambda sale: sale.gains.price, ordered_sales)), 2)}"
    )
    return ordered_sales
