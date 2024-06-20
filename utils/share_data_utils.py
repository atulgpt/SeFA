import pandas as pd
import os, sys
import date_utils
import logger
from ticker_mapping import ticker_currency_info

script_path = os.path.realpath(__file__)
script_folder = os.path.dirname(script_path)
sys.path.insert(1, os.path.join(script_folder, "rates"))
import rbi_rates_utils


def __validate_dates(historic_entry_time_in_millis, purchase_time_in_millis):
    if historic_entry_time_in_millis > purchase_time_in_millis:
        raise Exception(
            f"Historical FMV date {date_utils.log_timestamp(historic_entry_time_in_millis)} can NOT be newer than purchase date = {date_utils.log_timestamp(purchase_time_in_millis)}"
        )
    days_diff = (
        date_utils.last_work_day_in_millis(purchase_time_in_millis)
        - historic_entry_time_in_millis
    ) / (24 * 60 * 60 * 1000)

    date_utils.last_work_day_in_millis(purchase_time_in_millis)

    if days_diff > 0:
        msg = f"Historical FMV at {date_utils.log_timestamp(purchase_time_in_millis)} was NOT available last available(maybe due to Public Holiday) data is {int(days_diff)} days old(on {date_utils.display_time(historic_entry_time_in_millis)})"
        logger.log(msg)
        # if days_diff > 2:
        #     raise Exception(msg)


price_map = {}


def __init_map(ticker):
    if ticker not in price_map:
        print(f"Parsing FMV price map for ticker = {ticker}")
        ticker_price_map = []
        script_path = os.path.realpath(os.path.dirname(__file__))
        historic_share_path = os.path.join(
            script_path,
            os.pardir,
            "historic_data",
            "shares",
            ticker.lower(),
            "data.csv",
        )
        if not os.path.exists(historic_share_path):
            raise Exception(
                f"Historic share data for share {ticker} NOT present at {historic_share_path}"
            )
        df = pd.read_csv(historic_share_path)

        for index, data in df.iterrows():
            entry_time_in_millis = date_utils.parse_yyyy_mm_dd(data["Date"])[
                "time_in_millis"
            ]
            ticker_price_map.append(
                {"entry_time_in_millis": entry_time_in_millis, "fmv": data["Close"]}
            )

        price_map[ticker] = ticker_price_map

    return price_map[ticker]


def get_fmv(ticker, purchase_time_in_millis):
    logger.debug_log(
        f"Querying FMV at {date_utils.display_time(purchase_time_in_millis)} and ticker = {ticker}"
    )

    previous_entry = None
    for data in __init_map(ticker):
        entry_time_in_millis = data["entry_time_in_millis"]
        if entry_time_in_millis == purchase_time_in_millis:
            return data["fmv"]
        elif entry_time_in_millis > purchase_time_in_millis:
            previous_entry_time_in_millis = previous_entry["entry_time_in_millis"]
            __validate_dates(previous_entry_time_in_millis, purchase_time_in_millis)
            return previous_entry["fmv"]

        previous_entry = data

    raise Exception(
        f"Could NOT find FMV for share release at {date_utils.log_timestamp(purchase_time_in_millis)} and ticker = {ticker}"
    )


def closing_price(ticker, end_time_in_millis):
    price_map = list(
        filter(
            lambda price: price["entry_time_in_millis"] <= end_time_in_millis,
            sorted(
                __init_map(ticker),
                key=lambda price: price["entry_time_in_millis"],
                reverse=True,
            ),
        )
    )

    return price_map[0]["fmv"]


def peak_price_in_inr(ticker, start_time_in_millis, end_time_in_millis):
    if start_time_in_millis > end_time_in_millis:
        raise Exception(
            f"start_time_in_millis = {start_time_in_millis} is greater than equal to end_time_in_millis = {end_time_in_millis}"
        )

    logger.log(
        f"Searching peak price for ticker = {ticker} at start = {date_utils.log_timestamp(start_time_in_millis)}, end = {date_utils.log_timestamp(end_time_in_millis)}"
    )

    price_map = list(
        filter(
            lambda price: price["entry_time_in_millis"] <= end_time_in_millis
            and price["entry_time_in_millis"] >= start_time_in_millis,
            sorted(
                __init_map(ticker),
                key=lambda price: price["entry_time_in_millis"],
                reverse=True,
            ),
        )
    )
    price_map_with_inr_rate = map(
        lambda price: {
            **price,
            "inr_rate": rbi_rates_utils.get_rate_at_time_in_millis(
                ticker_currency_info[ticker], price["entry_time_in_millis"]
            ),
        },
        price_map,
    )

    max_value = max(
        price_map_with_inr_rate, key=lambda price: price["fmv"] * price["inr_rate"]
    )

    logger.debug_log_json(
        {
            "start_time": date_utils.display_time(start_time_in_millis),
            "end_time": date_utils.display_time(end_time_in_millis),
            "max_fmv($)": max_value["fmv"],
            "max_fmv($)_at": date_utils.display_time(max_value["entry_time_in_millis"]),
            "inr_conversion_rate": max_value["inr_rate"],
            "effective_price(INR)": max_value["fmv"] * max_value["inr_rate"],
        }
    )

    return max_value["fmv"] * max_value["inr_rate"]
