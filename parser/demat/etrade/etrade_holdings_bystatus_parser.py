import operator
from utils.runtime_utils import warn_missing_module
from utils.ticker_mapping import ticker_currency_info
from utils import logger, file_utils, date_utils

warn_missing_module("pandas")
import pandas as pd
import typing as t
import itertools

# from openpyxl import load_workbook

DEBUG = False

from models.purchase import Purchase, Price

SELLABLE_SHEET_NAME = "Sellable"


def parse_sellable_row(data: pd.Series) -> t.Optional[Purchase]:
    logger.debug_log(f"Currently parsing {type(data['Date Acquired'])} row")
    # skip this row if there is no date or date is not a string
    if data["Date Acquired"] is None or not isinstance(data["Date Acquired"], str):
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
    logger.debug_log(f"Currently parsing {SELLABLE_SHEET_NAME} sheet")
    sheet_pd = xl.parse(sheet_name=SELLABLE_SHEET_NAME, skiprows=0, header=0)
    purchases = []
    for _, data in sheet_pd.iterrows():
        parsed_purchase = parse_sellable_row(data)
        if parsed_purchase is not None:
            purchases.append(parsed_purchase)
    return purchases


def parse(input_file_abs_path: str, output_folder_abs_path: str) -> t.List[Purchase]:
    logger.DEBUG = DEBUG
    purchases: t.List[Purchase] = []
    with pd.ExcelFile(input_file_abs_path, engine="openpyxl") as xl:
        sheet_names = xl.sheet_names
        logger.log(f"Total sheets being process {sheet_names}")
        if SELLABLE_SHEET_NAME not in sheet_names:
            logger.log(f"Excel sheet don't have either {SELLABLE_SHEET_NAME}")
            return []
        purchases = parse_sellable(xl)

        # logger.log_json(espp_purchases)
        # logger.log_json(rsu_purchases)

    # purchases.sort(
    #    key=lambda purchase: purchase.date["time_in_millis"],
    # )
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
            f"{ticker}: Total shares present in the "
            + f"sheet = {sum(map(lambda x:x.quantity, ticker_shares_map[ticker]))}"
        )
    return purchases
