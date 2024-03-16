import sys
import os

script_path = os.path.realpath(__file__)
script_folder = os.path.dirname(script_path)
top_folder = os.path.dirname(os.path.dirname(script_folder))
sys.path.insert(1, os.path.join(top_folder, "utils"))
from ticker_mapping import ticker_org_info, ticker_currency_info
import date_utils
import share_data_utils
import file_utils

sys.path.insert(1, os.path.join(top_folder, "utils", "rates"))
import rbi_rates_utils

sys.path.insert(1, os.path.join(top_folder, "models"))
from purchase import Purchase, Price

sys.path.insert(1, os.path.join(top_folder, "models", "itr"))
from faa3 import FAA3

from itertools import groupby
import operator


day_fmv_map = {}


def __init_map():
    pass


def parse_org_purchases(
    ticker, calendar_mode, purchases, assessment_year, output_folder
):
    start_time_in_millis, end_time_in_millis = date_utils.calendar_range(
        calendar_mode, assessment_year
    )
    org = ticker_org_info[ticker]
    currency_code = ticker_currency_info[ticker]
    before_purchases = list(
        filter(
            lambda purchase: purchase.date["time_in_millis"] < start_time_in_millis,
            purchases,
        )
    )
    after_purchases = list(
        filter(
            lambda purchase: purchase.date["time_in_millis"] >= start_time_in_millis
            and purchase.date["time_in_millis"] <= end_time_in_millis,
            purchases,
        )
    )
    # for a in before_purchases:
    #     t = a.date["disp_time"]
    #     print(f"a = {a.quantity} on da = {t}")

    previous_sum = sum(map(lambda purchase: purchase.quantity, before_purchases))
    print(f"previous existing share total quantity({ticker}) = {previous_sum}")

    after_sum = sum(map(lambda purchase: purchase.quantity, after_purchases))
    print(f"this financial year total quantity({ticker}) = {after_sum}")

    fa_entries = []
    before_purchase_date = date_utils.parse_mm_dd(f"12/30/{assessment_year - 2}")
    closing_rbi_rate = rbi_rates_utils.get_rate_at_time_in_millis(
        currency_code, end_time_in_millis
    )
    closing_share_price = share_data_utils.closing_price(ticker, end_time_in_millis)
    closing_inr_price = closing_share_price * closing_rbi_rate
    print(
        f"Closing price(INR) = {closing_inr_price}, closing_share_price = {closing_share_price} closing_rbi_rate = {closing_rbi_rate}"
    )
    fmv_price_on_start = share_data_utils.get_fmv(
        ticker, before_purchase_date["time_in_millis"]
    )
    if previous_sum != 0:
        fa_entries.append(
            FAA3(
                org,
                purchase=Purchase(
                    before_purchase_date,
                    Price(
                        fmv_price_on_start,
                        ticker_currency_info[ticker],
                    ),
                    quantity=previous_sum,
                    ticker=ticker,
                ),
                purchase_price=previous_sum
                * fmv_price_on_start
                * rbi_rates_utils.get_rate_at_time_in_millis(
                    currency_code, start_time_in_millis
                ),
                peak_price=previous_sum
                * share_data_utils.peak_price_in_inr(
                    ticker, start_time_in_millis, end_time_in_millis
                ),
                closing_price=previous_sum * closing_inr_price,
            )
        )

    for purchase in after_purchases:
        fa_entries.append(
            FAA3(
                org,
                purchase=purchase,
                peak_price=purchase.quantity
                * share_data_utils.peak_price_in_inr(
                    ticker,
                    purchase.date["time_in_millis"],
                    end_time_in_millis,
                ),
                purchase_price=purchase.quantity
                * purchase.purchase_fmv.price
                * rbi_rates_utils.get_rate_at_time_in_millis(
                    currency_code, purchase.date["time_in_millis"]
                ),
                closing_price=purchase.quantity * closing_inr_price,
            )
        )

    file_utils.write_to_file(
        os.path.join(output_folder, ticker),
        "raw_fa_entries.json",
        fa_entries,
        True,
    )
    file_utils.write_to_file(
        os.path.join(output_folder, ticker),
        "raw_fa_entries.json",
        fa_entries,
        True,
    )
    file_utils.write_csv_to_file(
        os.path.join(output_folder, ticker),
        "fa_entries.csv",
        [
            "Country/Region Name and Code",
            "Name of Entity",
            "Address of Entity",
            "ZIP Code",
            "Nature of Entity",
            "Date of acquiring the interest",
            "Initial value of the investment",
            "Peak value of the investment during the Period",
            "Closing Value",
        ],
        map(
            lambda entry: (
                entry.org.country_name,
                entry.org.name,
                entry.org.address,
                entry.org.zip_code,
                entry.org.nature,
                entry.purchase.date["disp_time"],
                round(entry.purchase_price),
                round(entry.peak_price),
                round(entry.closing_price),
            ),
            fa_entries,
        ),
        True,
    )
    return fa_entries


def parse(calendar_mode, purchases, assessment_year, output_folder):
    ticker_attr = operator.attrgetter("ticker")
    grouped_list = groupby(sorted(purchases, key=ticker_attr), ticker_attr)

    for ticker, each_org_purchases in grouped_list:
        parse_org_purchases(
            ticker,
            calendar_mode,
            list(each_org_purchases),
            assessment_year,
            output_folder,
        )
