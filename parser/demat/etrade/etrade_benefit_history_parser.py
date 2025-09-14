import operator
from utils.runtime_utils import warn_missing_module
from utils import logger, file_utils, date_utils, share_data_utils
from utils.ticker_mapping import ticker_currency_info

warn_missing_module("pandas")
import pandas as pd
import typing as t
import itertools

# from openpyxl import load_workbook

DEBUG = False

from models.purchase import Purchase, Price

ESPP_SHEET_NAME = "ESPP"
RSU_SHEET_NAME = "Restricted Stock"


def parse_espp_row(data: pd.Series) -> t.Optional[Purchase]:
    if data["Record Type"] == "Purchase":
        return Purchase(
            date=date_utils.parse_named_mon(data["Purchase Date"]),
            purchase_fmv=Price(
                float(data["Purchase Date FMV"][1:]),
                ticker_currency_info[data["Symbol"].lower()],
            ),
            quantity=float(data["Sellable Qty."]),
            ticker=data["Symbol"].lower(),
        )
    return None


def parse_espp(
    xl: pd.ExcelFile, time_bounds: t.Optional[date_utils.DateBounds]
) -> t.List[Purchase]:
    logger.debug_log(f"Currently parsing {ESPP_SHEET_NAME} sheet")
    sheet_pd = xl.parse(sheet_name=ESPP_SHEET_NAME, skiprows=0, header=0)
    purchases = []
    for _, data in sheet_pd.iterrows():
        parsed_purchase = parse_espp_row(data)
        if parsed_purchase is not None:
            purchases.append(parsed_purchase)
    return purchases


def parse_rsu_row(data: pd.Series, ticker: str) -> t.Optional[Purchase]:
    if data["Event Type"] == "Shares released":
        ticker_in_lower = ticker.lower()
        return Purchase(
            date=date_utils.parse_mm_dd(data["Date"]),
            purchase_fmv=Price(
                share_data_utils.get_fmv(
                    ticker_in_lower,
                    date_utils.parse_mm_dd(data["Date"])["time_in_millis"],
                ),
                ticker_currency_info[ticker_in_lower],
            ),
            quantity=data["Qty. or Amount"],
            ticker=ticker_in_lower,
        )
    return None


def parse_rsu(
    xl: pd.ExcelFile,
    time_bounds: t.Optional[date_utils.DateBounds],
):
    logger.debug_log(f"Currently parsing {RSU_SHEET_NAME} sheet")
    sheet_pd = xl.parse(sheet_name=RSU_SHEET_NAME, skiprows=0, header=0)
    purchases: t.List[Purchase] = []
    current_ticker = None
    for _, data in sheet_pd.iterrows():
        if data["Record Type"] == "Grant":
            current_ticker = data["Symbol"].lower()
        if data["Event Type"] == "Shares released":
            if not date_utils.is_in_bounds(
                date_utils.parse_mm_dd(data["Date"])["time_in_millis"], time_bounds
            ):
                continue
            assert current_ticker is not None, (
                f"There is RSU event({data["Event Type"]}) without Grant event(which contains the ticker info)"
                + f" hence no ticker info is found while parsing {RSU_SHEET_NAME}"
            )
            parsed_purchase = parse_rsu_row(data, current_ticker)
            if parsed_purchase is not None:
                purchases.append(parsed_purchase)
    return purchases


def parse(
    input_file_abs_path: str,
    output_folder_abs_path: str,
    time_bounds: t.Optional[date_utils.DateBounds],
) -> t.List[Purchase]:
    logger.DEBUG = DEBUG
    purchases: t.List[Purchase] = []
    with pd.ExcelFile(input_file_abs_path, engine="openpyxl") as xl:
        sheet_names = xl.sheet_names
        logger.log(f"Total sheets being process {sheet_names}")
        if ESPP_SHEET_NAME not in sheet_names and RSU_SHEET_NAME not in sheet_names:
            logger.log(
                f"Excel sheet don't have either {ESPP_SHEET_NAME} or {RSU_SHEET_NAME}"
            )
            return []
        espp_purchases = parse_espp(xl, time_bounds)
        purchases.extend(espp_purchases)

        rsu_purchases = parse_rsu(xl, time_bounds)
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
            f"{ticker}: Total shares present in the sheet "
            + f"= {sum(map(lambda x:x.quantity, ticker_shares_map[ticker]))}"
        )
    return purchases
