import csv
import os
import typing as t
from itertools import groupby
import operator

from sefa.utils import date_utils, file_utils
from sefa.utils.date_utils import CalendarMode
from sefa.utils import share_data_utils
from sefa.utils.ticker_mapping import ticker_org_info, ticker_currency_info
from sefa.utils.rates import rbi_rates_utils
from sefa.models.transaction import TransactionWithTicker
from sefa.models.itr.faa3 import FAA3, FAA3_CSV_HEADER_COLUMNS, FAA3CsvEntries
from sefa.models.section_type import SectionType
from sefa.models.section_data import SectionDataMap

FA_ENTRIES_OUTPUT_FILE_NAME = "fa_entries.csv"

# every schedule FA source is held with the same broker, so its raw workings share
# one folder and are told apart by the operation mode they were read from
RAW_FOLDER_NAME = "etrade"
RAW_FA_ENTRIES_FILE_NAME_FORMAT = "fa_raw_{operation_mode}_entries.json"
RAW_FA_ENTRIES_CSV_FILE_NAME_FORMAT = "fa_raw_{operation_mode}_entries.csv"


def parse_org_purchases(
    ticker: str,
    calendar_mode: CalendarMode,
    purchases: t.List[TransactionWithTicker],
    assessment_year: int,
) -> t.List[FAA3]:
    start_time_in_ms, end_time_in_ms = date_utils.calendar_range(
        calendar_mode, assessment_year
    )
    org = ticker_org_info[ticker]
    currency_code = ticker_currency_info[ticker]
    before_purchases = list(
        filter(
            lambda purchase: purchase.purchase.date["time_in_millis"]
            < start_time_in_ms,
            purchases,
        )
    )
    after_purchases = list(
        filter(
            lambda purchase: purchase.purchase.date["time_in_millis"]
            >= start_time_in_ms
            and purchase.purchase.date["time_in_millis"] <= end_time_in_ms,
            purchases,
        )
    )
    # for a in before_purchases:
    #     t = a.purchase.date["disp_time"]
    #     print(f"a = {a.purchase.quantity} on da = {t}")

    previous_sum = sum(
        map(lambda purchase: purchase.purchase.quantity, before_purchases)
    )
    print(
        f"{ticker}: Previous period(before {date_utils.display_time(start_time_in_ms)}) total share = {previous_sum}"
    )

    after_sum = sum(map(lambda purchase: purchase.purchase.quantity, after_purchases))
    print(
        f"{ticker}: This period(from {date_utils.display_time(start_time_in_ms)} to {date_utils.display_time(end_time_in_ms)}) total share = {after_sum}"
    )

    fa_entries: t.List[FAA3] = []
    before_purchases_last_date = f"31-Dec-{assessment_year - 2}"
    before_purchase_date = date_utils.parse_named_mon(before_purchases_last_date)
    closing_rbi_rate = rbi_rates_utils.get_rate_for_prev_mon_for_time_in_ms(
        currency_code, end_time_in_ms
    )
    closing_share_price = share_data_utils.get_closing_price(ticker, end_time_in_ms)
    closing_inr_price = closing_share_price * closing_rbi_rate
    print(
        f"{ticker}: Closing price(INR) = {closing_inr_price}, closing_share_price({ticker_currency_info[ticker]}) = {closing_share_price} closing_rbi_rate(INR) = {closing_rbi_rate}"
    )
    fmv_price_on_start = share_data_utils.get_fmv(
        ticker, before_purchase_date["time_in_millis"]
    )
    print(
        f"{ticker}: Queried FMV on {before_purchases_last_date} is {fmv_price_on_start}. This is used for accumulated sum for previous purchases"
    )
    if previous_sum != 0:
        fa_entries.append(
            FAA3(
                org,
                purchase_date=before_purchase_date,
                purchase_price=previous_sum
                * fmv_price_on_start
                * rbi_rates_utils.get_rate_for_prev_mon_for_time_in_ms(
                    currency_code, start_time_in_ms
                ),
                peak_price=previous_sum
                * share_data_utils.get_peak_price_in_inr(
                    ticker, start_time_in_ms, end_time_in_ms
                ),
                closing_price=previous_sum * closing_inr_price,
            )
        )

    for purchase in after_purchases:
        fa_entries.append(
            FAA3(
                org,
                purchase_date=purchase.purchase.date,
                peak_price=purchase.purchase.quantity
                * share_data_utils.get_peak_price_in_inr(
                    ticker,
                    purchase.purchase.date["time_in_millis"],
                    end_time_in_ms,
                ),
                purchase_price=purchase.purchase.quantity
                * purchase.purchase.fmv.price
                * rbi_rates_utils.get_rate_for_prev_mon_for_time_in_ms(
                    currency_code, purchase.purchase.date["time_in_millis"]
                ),
                closing_price=purchase.purchase.quantity * closing_inr_price,
            )
        )

    return fa_entries


def __rows(fa_entries: t.List[FAA3]) -> t.Iterator[FAA3CsvEntries]:
    return (entry.as_csv_entries() for entry in fa_entries)


def write_fa_entries(
    fa_entries: t.List[FAA3],
    output_folder_abs_path: str,
) -> None:
    """
    The schedule FA under section A3 upload, holding the entries of every source
    and every ticker of the run
    """
    file_utils.write_csv_to_file(
        output_folder_abs_path,
        FA_ENTRIES_OUTPUT_FILE_NAME,
        FAA3_CSV_HEADER_COLUMNS,
        __rows(fa_entries),
        True,
        print_path_to_console=True,
        data_quoting=csv.QUOTE_NONE,
    )


def parse(
    operation_mode: str,
    calendar_mode: CalendarMode,
    purchases: t.List[TransactionWithTicker],
    assessment_year: int,
    output_folder_abs_path: str,
) -> SectionDataMap:
    """
    Entries of one source, its own raw workings written aside for a cross check
    """
    ticker_attr = operator.attrgetter("ticker")
    grouped_list = groupby(sorted(purchases, key=ticker_attr), ticker_attr)

    fa_entries: t.List[FAA3] = []
    for ticker, each_org_purchases in grouped_list:
        fa_entries.extend(
            parse_org_purchases(
                ticker,
                calendar_mode,
                list(each_org_purchases),
                assessment_year,
            )
        )

    raw_folder_abs_path = os.path.join(
        output_folder_abs_path, file_utils.RAW_OUTPUT_FOLDER_NAME, RAW_FOLDER_NAME
    )
    file_utils.write_to_file(
        raw_folder_abs_path,
        RAW_FA_ENTRIES_FILE_NAME_FORMAT.format(operation_mode=operation_mode),
        fa_entries,
        True,
    )
    file_utils.write_csv_to_file(
        raw_folder_abs_path,
        RAW_FA_ENTRIES_CSV_FILE_NAME_FORMAT.format(operation_mode=operation_mode),
        FAA3_CSV_HEADER_COLUMNS,
        __rows(fa_entries),
        True,
        print_path_to_console=True,
        data_quoting=csv.QUOTE_NONE,
    )
    return SectionDataMap({SectionType.SCHEDULE_FA_A3: list(fa_entries)})
