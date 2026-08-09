import csv
import os
import typing as t
from itertools import groupby
import operator

from utils import date_utils, share_data_utils, file_utils
from utils.ticker_mapping import ticker_org_info, ticker_currency_info
from utils.rates import rbi_rates_utils
from models.transaction import Transaction, TransactionWithTicker, Price
from models.itr.faa3 import FAA3
from models.section_type import SectionType
from models.section_data import SectionDataMap

FA_ENTRIES_OUTPUT_FILE_NAME = "fa_entries.csv"

# every schedule FA source is held with the same broker, so its raw workings share
# one folder and are told apart by the operation mode they were read from
RAW_FOLDER_NAME = "etrade"
RAW_FA_ENTRIES_FILE_NAME_FORMAT = "fa_raw_{operation_mode}_entries.json"
RAW_FA_ENTRIES_CSV_FILE_NAME_FORMAT = "fa_raw_{operation_mode}_entries.csv"

FA_ENTRIES_COLUMNS = [
    "Country/Region name",
    "Country Name and Code",
    "Name of entity",
    "Address of entity",
    "ZIP Code",
    "Nature of entity",
    "Date of acquiring the interest",
    "Initial value of the investment",
    "Peak value of investment during the Period",
    "Closing balance",
    "Total gross amount paid/credited with respect to the holding during the period",
    "Total gross proceeds from sale or redemption of investment during the period",
]


def parse_org_purchases(
    ticker: str,
    calendar_mode: str,
    purchases: t.List[TransactionWithTicker],
    assessment_year: int,
    output_folder_abs_path: str,
):
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


def __rows(fa_entries: t.List[FAA3]):
    return map(
        lambda entry: (
            entry.org.country_name,
            entry.org.country_code,
            entry.org.name,
            entry.org.address,
            entry.org.zip_code,
            entry.org.nature,
            # ref https://www.reddit.com/r/IndiaTax/comments/1mhbi0w/a3_template_commonerrorscsv_row_skip_any_idea/
            date_utils.format_time(entry.purchase_date["time_in_millis"], "%Y-%m-%d"),
            round(entry.purchase_price),
            round(entry.peak_price),
            round(entry.closing_price),
            round(entry.gross_amount_paid),
            round(entry.gross_sale_proceeds),
        ),
        fa_entries,
    )


def write_fa_entries(
    fa_entries: t.List[FAA3],
    output_folder_abs_path: str,
):
    """
    The schedule FA under section A3 upload, holding the entries of every source
    and every ticker of the run
    """
    file_utils.write_csv_to_file(
        output_folder_abs_path,
        FA_ENTRIES_OUTPUT_FILE_NAME,
        FA_ENTRIES_COLUMNS,
        __rows(fa_entries),
        True,
        print_path_to_console=True,
        data_quoting=csv.QUOTE_NONE,
    )


def parse(
    operation_mode: str,
    calendar_mode: str,
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
                output_folder_abs_path,
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
        FA_ENTRIES_COLUMNS,
        __rows(fa_entries),
        True,
        print_path_to_console=True,
        data_quoting=csv.QUOTE_NONE,
    )
    return {SectionType.SCHEDULE_FA_A3: fa_entries}
