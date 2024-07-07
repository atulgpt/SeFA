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

sellable_sheet_name = "Sellable"

def parse_sellable_row(data: pd.Series) -> t.Optional[Purchase]:
    logger.debug_log(f"Currently parsing {type(data["Date Acquired"])} row")
    # skip this row if there is no date or date is not a string
    if data["Date Acquired"] == None or not isinstance(data["Date Acquired"], str):
        return None
    
    return Purchase(
        date=date_utils.parse_named_mon(data["Date Acquired"]),
        purchase_fmv=Price(
            float(data["Purchase Date FMV"][1:]),
            ticker_currency_info[data["Symbol"].lower()],
        ),
        quantity=data["Sellable Qty."],
        ticker=data["Symbol"].lower(),
    )

def parse_sellable(xl: pd.ExcelFile) -> t.List[Purchase]:
    logger.debug_log(f"Currently parsing {sellable_sheet_name} sheet")
    sheet_pd = xl.parse(sheet_name=sellable_sheet_name, skiprows=0, header=0)
    purchases = []
    for _, data in sheet_pd.iterrows():
        parsed_purchase = parse_sellable_row(data)
        if parsed_purchase != None:
            purchases.append(parsed_purchase)
    return purchases


def parse(input_file_abs_path: str, output_folder_abs_path: str) -> t.List[Purchase]:
    logger.debug = debug
    purchases: t.List[Purchase] = []
    with pd.ExcelFile(input_file_abs_path, engine="openpyxl") as xl:
        sheet_names = xl.sheet_names
        logger.log(f"Total sheets being process {sheet_names}")
        if sellable_sheet_name not in sheet_names:
            logger.log(
                f"Excel sheet don't have either {sellable_sheet_name}"
            )
            return []
        purchases = parse_sellable(xl)

        # logger.log_json(espp_purchases)
        # logger.log_json(rsu_purchases)

    #purchases.sort(
    #    key=lambda purchase: purchase.date["time_in_millis"],
    #)
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
