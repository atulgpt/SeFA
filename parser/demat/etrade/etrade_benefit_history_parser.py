import operator
import os
from utils.runtime_utils import warn_missing_module
from utils import logger, file_utils, date_utils, share_data_utils
from utils.ticker_mapping import ticker_currency_info

warn_missing_module("pandas")
import pandas as pd
import typing as t
import itertools

# from openpyxl import load_workbook

DEBUG = False

from models.transaction import Transaction, TransactionWithTicker, Price
from models.section_data import SectionDataMap
from parser.itr import faa3_parser

# raw workings of this source, told apart by the operation mode they were read from
PURCHASES_OUTPUT_FILE_NAME = "purchases_etrade_benefit_history.json"

ESPP_SHEET_NAME = "ESPP"
RSU_SHEET_NAME = "Restricted Stock"


def parse_espp_row(data: pd.Series) -> t.Optional[TransactionWithTicker]:
    if data["Record Type"] == "Purchase":
        return TransactionWithTicker(
            purchase=Transaction(
                date=date_utils.parse_named_mon(data["Purchase Date"]),
                fmv=Price(
                    float(data["Purchase Date FMV"][1:]),
                    ticker_currency_info[data["Symbol"].lower()],
                ),
                quantity=float(data["Sellable Qty."]),
            ),
            ticker=data["Symbol"].lower(),
        )
    return None


def parse_espp(
    xl: pd.ExcelFile, time_bounds_in_ms: t.Optional[date_utils.DateBoundsInMs]
) -> t.List[TransactionWithTicker]:
    logger.debug_log(f"Currently parsing {ESPP_SHEET_NAME} sheet")
    sheet_pd = xl.parse(sheet_name=ESPP_SHEET_NAME, skiprows=0, header=0)
    purchases = []
    for _, data in sheet_pd.iterrows():
        parsed_purchase = parse_espp_row(data)
        if parsed_purchase is not None:
            purchases.append(parsed_purchase)
    return purchases


def parse_rsu_row(data: pd.Series, ticker: str) -> t.Optional[TransactionWithTicker]:
    if data["Event Type"] == "Shares released":
        ticker_in_lower = ticker.lower()
        return TransactionWithTicker(
            purchase=Transaction(
                date=date_utils.parse_mm_dd(data["Date"]),
                fmv=Price(
                    share_data_utils.get_fmv(
                        ticker_in_lower,
                        date_utils.parse_mm_dd(data["Date"])["time_in_millis"],
                    ),
                    ticker_currency_info[ticker_in_lower],
                ),
                quantity=data["Qty. or Amount"],
            ),
            ticker=ticker_in_lower,
        )
    return None


def parse_rsu(
    xl: pd.ExcelFile,
    time_bounds_in_ms: t.Optional[date_utils.DateBoundsInMs],
):
    logger.debug_log(f"Currently parsing {RSU_SHEET_NAME} sheet")
    sheet_pd = xl.parse(sheet_name=RSU_SHEET_NAME, skiprows=0, header=0)
    purchases: t.List[TransactionWithTicker] = []
    current_ticker = None
    for _, data in sheet_pd.iterrows():
        if data["Record Type"] == "Grant":
            current_ticker = data["Symbol"].lower()
        if data["Event Type"] == "Shares released":
            if not date_utils.is_in_bounds(
                date_utils.parse_mm_dd(data["Date"])["time_in_millis"], time_bounds_in_ms
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
    operation_mode: str,
    calendar_mode: str,
    assessment_year: int,
    time_bounds_in_ms: t.Optional[date_utils.DateBoundsInMs],
) -> SectionDataMap:
    logger.DEBUG = DEBUG
    purchases: t.List[TransactionWithTicker] = []
    with pd.ExcelFile(input_file_abs_path, engine="openpyxl") as xl:
        sheet_names = xl.sheet_names
        logger.log(f"Total sheets being process {sheet_names}")
        if ESPP_SHEET_NAME not in sheet_names and RSU_SHEET_NAME not in sheet_names:
            logger.log(
                f"Excel sheet don't have either {ESPP_SHEET_NAME} or {RSU_SHEET_NAME}"
            )
            return []
        espp_purchases = parse_espp(xl, time_bounds_in_ms)
        purchases.extend(espp_purchases)

        rsu_purchases = parse_rsu(xl, time_bounds_in_ms)
        purchases.extend(rsu_purchases)

        # logger.log_json(espp_purchases)
        # logger.log_json(rsu_purchases)

    purchases.sort(
        key=lambda purchase: purchase.purchase.date["time_in_millis"],
    )
    file_utils.write_to_file(
        os.path.join(
            output_folder_abs_path,
            file_utils.RAW_OUTPUT_FOLDER_NAME,
            faa3_parser.RAW_FOLDER_NAME,
        ),
        PURCHASES_OUTPUT_FILE_NAME,
        purchases,
        True,
    )

    ticker_shares_map: t.Dict[str, list[TransactionWithTicker]] = {}
    for ticker, ticker_purchases in itertools.groupby(
        purchases, key=operator.attrgetter("ticker")
    ):
        ticker_shares_map[ticker] = list(ticker_purchases)
        print(
            f"{ticker}: Total shares present in the sheet "
            + f"= {sum(map(lambda x:x.purchase.quantity, ticker_shares_map[ticker]))}"
        )
    return faa3_parser.parse(
        operation_mode,
        calendar_mode,
        purchases,
        assessment_year,
        output_folder_abs_path,
    )
