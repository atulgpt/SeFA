import sys, os, json
import pandas as pd
from datetime import datetime, timedelta

sys.path.insert(1, "..")
import date_utils
import logger

rate_map = {}


def __init_map(currency_code):
    if currency_code not in rate_map:
        print(f"Parsing rbi rate for currency code = {currency_code}")
        currency_rate_map = {}
        script_path = os.path.realpath(os.path.dirname(__file__))
        rbi_rates_file_path = os.path.join(
            script_path,
            os.pardir,
            os.pardir,
            "historic_data",
            "rates",
            "rbi",
            "rates.xls",
        )

        if not os.path.exists(rbi_rates_file_path):
            raise Exception(f"Rbi rates file {rbi_rates_file_path} is NOT present")

        with pd.ExcelFile(rbi_rates_file_path, engine="openpyxl") as xl:
            logger.debug_log(f"Currently parsing Reference Rates sheet")
            sheet_pd = xl.parse(sheet_name="Reference Rates", skiprows=0, header=2)
            for index, data in sheet_pd.iterrows():
                if data["Currency Pairs"] == f"INR / 1 {currency_code.upper()}":
                    rate_time = datetime.strptime(data["Date"], "%d %b %Y")
                    if (
                        rate_time.year not in currency_rate_map
                        or rate_time.month not in currency_rate_map[rate_time.year]
                        or currency_rate_map[rate_time.year][rate_time.month][
                            "time_in_millis"
                        ]
                        < date_utils.__epoch(rate_time)
                    ):
                        currency_rate_map[rate_time.year] = currency_rate_map.get(
                            rate_time.year, {}
                        )
                        currency_rate_map[rate_time.year][rate_time.month] = {
                            "time_in_millis": date_utils.__epoch(rate_time),
                            "rate": data["Rate"],
                        }

            rate_map[currency_code] = currency_rate_map

    return rate_map[currency_code]


def get_rate_at_month(currency_code, month, year):
    rate_month, rate_year = (month - 1, year) if month != 1 else (12, year - 1)
    return __init_map(currency_code)[rate_year][rate_month]["rate"]


def get_rate_at_time_in_millis(currency_code, time_in_millis):
    dt = datetime.utcfromtimestamp(time_in_millis / 1000)
    return get_rate_at_month(currency_code, dt.month, dt.year)
