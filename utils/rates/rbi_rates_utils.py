import sys, os
import pandas as pd
from datetime import datetime
import typing as t

script_path = os.path.realpath(__file__)
script_folder = os.path.dirname(script_path)
top_folder = os.path.dirname(os.path.dirname(script_folder))
sys.path.insert(1, os.path.join(top_folder, "utils"))
import date_utils
import logger


class RbiRateObj(t.TypedDict):
    time_in_millis: int
    rate: float


RbiYearMonthRateMap = t.Dict[int, t.Dict[int, RbiRateObj]]
RbiCurrencyToRateMap = t.Dict[str, RbiYearMonthRateMap]

rate_map_cache: RbiCurrencyToRateMap = {}


def __init_map(currency_code: str) -> RbiYearMonthRateMap:
    if currency_code not in rate_map_cache:
        print(f"Parsing rbi rate for currency code = {currency_code}")
        currency_rate_map: RbiYearMonthRateMap = {}
        script_path = os.path.realpath(os.path.dirname(__file__))
        rbi_rates_file_abs_path = os.path.join(
            script_path,
            os.pardir,
            os.pardir,
            "historic_data",
            "rates",
            "rbi",
            "rates.xls",
        )
        if not os.path.exists(rbi_rates_file_abs_path):
            raise Exception(f"RBI rates.xls {rbi_rates_file_abs_path} is NOT present")

        with pd.ExcelFile(rbi_rates_file_abs_path, engine="openpyxl") as xl:
            logger.debug_log(f"Currently parsing Reference Rates sheet")
            sheet_pd = xl.parse(sheet_name="Reference Rates", skiprows=0, header=2)
            for _, data in sheet_pd.iterrows():
                if data["Currency Pairs"] == f"INR / 1 {currency_code.upper()}":
                    rate_time = datetime.strptime(data["Date"], "%d %b %Y")
                    if (
                        rate_time.year not in currency_rate_map
                        or rate_time.month not in currency_rate_map[rate_time.year]
                        or currency_rate_map[rate_time.year][rate_time.month][
                            "time_in_millis"
                        ]
                        < date_utils.epoch_in_ms(rate_time)
                    ):
                        currency_rate_map[rate_time.year] = currency_rate_map.get(
                            rate_time.year, {}
                        )
                        currency_rate_map[rate_time.year][rate_time.month] = {
                            "time_in_millis": date_utils.epoch_in_ms(rate_time),
                            "rate": data["Rate"],
                        }

            rate_map_cache[currency_code] = currency_rate_map

    return rate_map_cache[currency_code]


def get_rate_at_month(currency_code: str, month: int, year: int) -> float:
    return __init_map(currency_code)[year][month]["rate"]


def get_rate_for_prev_mon_for_time_in_ms(currency_code: str, time_in_ms: int) -> float:
    dt = datetime.utcfromtimestamp(time_in_ms / 1000)
    month = dt.month
    year = dt.year
    rate_month, rate_year = (month - 1, year) if month != 1 else (12, year - 1)
    return get_rate_at_month(currency_code, rate_month, rate_year)
