import operator
import sys, os
import pandas as pd
import typing as t
import itertools

# from openpyxl import load_workbook

debug = False

script_path = os.path.realpath(__file__)
script_folder = os.path.dirname(script_path)
top_folder = os.path.dirname(os.path.dirname(script_folder))
sys.path.insert(1, os.path.join(top_folder, "utils"))
from ticker_mapping import ticker_currency_info
import logger
import file_utils
import date_utils
import share_data_utils

sys.path.insert(1, os.path.join(top_folder, "models"))
from purchase import Purchase, Price

espp_sheet_name = "ESPP"
rsu_sheet_name = "Restricted Stock"


def parse_espp_row(data: pd.Series) -> t.Optional[Purchase]:
    if data["Record Type"] == "Purchase":
        return Purchase(
            date=date_utils.parse_named_mon(data["Purchase Date"]),
            purchase_fmv=Price(
                float(data["Purchase Date FMV"][1:]),
                ticker_currency_info[data["Symbol"].lower()],
            ),
            quantity=data["Sellable Qty."],
            ticker=data["Symbol"].lower(),
        )
    else:
        return None


def parse_espp(xl: pd.ExcelFile) -> t.List[Purchase]:
    logger.debug_log(f"Currently parsing {espp_sheet_name} sheet")
    sheet_pd = xl.parse(sheet_name=espp_sheet_name, skiprows=0, header=0)
    purchases = []
    for _, data in sheet_pd.iterrows():
        parsed_purchase = parse_espp_row(data)
        if parsed_purchase != None:
            purchases.append(parsed_purchase)
    return purchases


def calculate_rsu_fmv(xl: pd.ExcelFile, date, grant) -> float:
    sheet_pd = xl.parse(sheet_name=rsu_sheet_name, skiprows=0, header=0)
    vested_row = None
    for _, data in sheet_pd.iterrows():
        if (
            data["Record Type"] == "Vest Schedule"
            and data["Vest Date"] == date
            and data["Grant Number"] == grant
        ):
            vested_row = data
            continue
        elif data["Record Type"] == "Tax Withholding" and vested_row is not None:
            fmv: float = data["Taxable Gain"] / vested_row["Vested Qty..1"]
            vested_row = None
            return fmv

    raise Exception(
        f"Could NOT find FMV for share release at {date} and grant = {grant}"
    )


def parse_rsu_row(data: pd.Series, ticker: str) -> t.Optional[Purchase]:
    if data["Event Type"] == "Shares released":
        return Purchase(
            date=date_utils.parse_mm_dd(data["Date"]),
            purchase_fmv=Price(
                share_data_utils.get_fmv(
                    ticker, date_utils.parse_mm_dd(data["Date"])["time_in_millis"]
                ),
                # calculate_rsu_fmv(xl, data["Date"], data["Grant Number"]),
                ticker_currency_info[ticker],
            ),
            quantity=data["Qty. or Amount"],
            ticker=ticker,
        )
    else:
        return None


def parse_rsu(xl: pd.ExcelFile):
    logger.debug_log(f"Currently parsing {rsu_sheet_name} sheet")
    sheet_pd = xl.parse(sheet_name=rsu_sheet_name, skiprows=0, header=0)
    purchases: t.List[Purchase] = []
    current_ticker = None
    for _, data in sheet_pd.iterrows():
        if data["Record Type"] == "Grant":
            current_ticker = data["Symbol"].lower()
        parsed_purchase = parse_rsu_row(data, current_ticker)
        if parsed_purchase != None:
            purchases.append(parsed_purchase)
    return purchases


def parse(input_file_abs_path: str, output_folder_abs_path: str) -> t.List[Purchase]:
    logger.debug = debug
    purchases: t.List[Purchase] = []
    with pd.ExcelFile(input_file_abs_path, engine="openpyxl") as xl:
        sheet_names = xl.sheet_names
        logger.log(f"Total sheets being process {sheet_names}")
        if espp_sheet_name not in sheet_names and rsu_sheet_name not in sheet_names:
            logger.log(
                f"Excel sheet don't have either {espp_sheet_name} or {rsu_sheet_name}"
            )
            return []
        espp_purchases = parse_espp(xl)
        purchases.extend(espp_purchases)

        rsu_purchases = parse_rsu(xl)
        purchases.extend(rsu_purchases)

        # logger.log_json(espp_purchases)
        # logger.log_json(rsu_purchases)

    purchases.sort(
        key=lambda purchase: purchase.date["time_in_millis"],
    )
    file_utils.write_to_file(
        output_folder_abs_path,
        "purchases.json",
        purchases,
        True,
    )

    ticker_shares_map: t.Dict[str, list[Purchase]] = {}
    for ticker, ticker_purchases in itertools.groupby(
        purchases, key=operator.attrgetter("ticker")
    ):
        ticker_shares_map[ticker] = list(ticker_purchases)
        print(
            f"{ticker}: Total shares present in the sheet = {sum(map(lambda x:x.quantity, ticker_shares_map[ticker]))}"
        )
    return purchases
