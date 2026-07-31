#!/usr/bin/env python3
import argparse
import os
import sys
import typing as t

from datetime import date, timedelta

from parser.demat.etrade import etrade_benefit_history_parser
from utils import logger, date_utils
from parser.demat.etrade import etrade_holdings_bystatus_parser
from parser.demat.indmoney import indmoney_us_stocks_parser
from parser.demat.groww import groww_indian_mf_parser, groww_indian_stocks_parser
from models.asset_sale import AssetSale
from parser.itr import faa3_parser
from aggregator import asset_aggregator
from utils.ticker_mapping import ticker_currency_info, ticker_org_info
from refresh_historic_data import refresh, DEFAULT_START
import refresh_rbi_rates

# arguments defaults
script_path = os.path.realpath(os.path.dirname(__file__))
DEFAULT_OUTPUT_FOLDER_NAME = "output"
default_output_folder_abs_path = os.path.join(script_path, DEFAULT_OUTPUT_FOLDER_NAME)
DEFAULT_SOURCE_MODE = "etrade_benefit_history"
ETRADE_HOLDINGS_BYSTATUS_SOURCE_MODE = "etrade_holdings_bystatus"
INDMONEY_US_STOCKS_SOURCE_MODE = "indmoney_us_stocks"
GROWW_INDIAN_STOCKS_SOURCE_MODE = "groww_indian_stocks"
GROWW_INDIAN_MF_SOURCE_MODE = "groww_indian_mf"

# Source modes reporting realized sales, which schedule FA under section A3 does
# not consume. A mode lists every parser that reads a table out of that source's
# report, their sales being aggregated together
SALE_SOURCE_PARSERS = {
    INDMONEY_US_STOCKS_SOURCE_MODE: (indmoney_us_stocks_parser,),
    GROWW_INDIAN_STOCKS_SOURCE_MODE: (groww_indian_stocks_parser,),
    GROWW_INDIAN_MF_SOURCE_MODE: (groww_indian_mf_parser,),
}

SOURCE_MODES = [
    DEFAULT_SOURCE_MODE,
    ETRADE_HOLDINGS_BYSTATUS_SOURCE_MODE,
    *SALE_SOURCE_PARSERS,
]
DEFAULT_CALENDER_MODE = "calendar"
FINANCIAL_CALENDER_MODE = "financial"
CALENDER_MODES = [
    DEFAULT_CALENDER_MODE,
    FINANCIAL_CALENDER_MODE,
]


def main():
    parser = argparse.ArgumentParser(
        description="This is a Python module to generate Indian ITR schedule FA under section A3 automatically"
    )
    parser.add_argument(
        "-o",
        "--output",
        action="store",
        type=str,
        default=default_output_folder_abs_path,
        dest="output_folder",
        help=f"Specify the absolute path of the absolute path of output folder for JSON data, default = {default_output_folder_abs_path}",
    )
    parser.add_argument(
        "-i",
        "--input",
        action="store",
        dest="input_excel_file",
        help="Specify the absolute path for the input Excel file of the chosen source"
        f" mode: benefit history(BenefitHistory.xlsx) for {DEFAULT_SOURCE_MODE},"
        f" holdings by status for {ETRADE_HOLDINGS_BYSTATUS_SOURCE_MODE}, the"
        f" consolidated tax report for {INDMONEY_US_STOCKS_SOURCE_MODE} and the"
        " stocks/mutual funds capital gains statement for"
        f" {GROWW_INDIAN_STOCKS_SOURCE_MODE}/{GROWW_INDIAN_MF_SOURCE_MODE}",
        required=True,
    )
    parser.add_argument(
        "-m",
        "--source-mode",
        action="store",
        default=DEFAULT_SOURCE_MODE,
        dest="source_mode",
        choices=SOURCE_MODES,
        help=f"Specify the source mode, default = {DEFAULT_SOURCE_MODE}."
        f" {', '.join(SALE_SOURCE_PARSERS)} report realized sales and do not feed"
        " the schedule FA generation",
    )
    parser.add_argument(
        "-cal",
        "--calendar-mode",
        action="store",
        type=str,
        default=DEFAULT_CALENDER_MODE,
        dest="calendar_mode",
        choices=CALENDER_MODES,
        help=f"Specify the calendar period for consideration, default = {DEFAULT_CALENDER_MODE}",
    )
    parser.add_argument(
        "-ay",
        "--assessment-year",
        action="store",
        dest="assessment_year",
        type=int,
        required=True,
        help="Current year of assessment year. For AY 2019-2020, input will be 2019. Input will be of type integer",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        dest="debug",
        default=False,
        help="Enable the debug logs",
    )
    parser.add_argument(
        "--skip-refresh",
        action="store_true",
        dest="skip_refresh",
        default=False,
        help="Skip refreshing historic share prices from Yahoo Finance and use the "
        "bundled historic_data CSVs instead (useful when offline)",
    )

    args = parser.parse_args()

    logger.DEBUG = args.debug
    etrade_benefit_history_parser.DEBUG = args.debug
    etrade_holdings_bystatus_parser.DEBUG = args.debug
    for sale_source_parsers in SALE_SOURCE_PARSERS.values():
        for sale_source_parser in sale_source_parsers:
            sale_source_parser.DEBUG = args.debug
    asset_aggregator.DEBUG = args.debug

    # Refresh before parsing: RSU rows resolve their FMV from the share price CSV
    # during parsing, so the historic data must be up to date beforehand.
    if not args.skip_refresh:
        refresh_historic_data()

    if args.source_mode in SALE_SOURCE_PARSERS:
        time_bounds = date_utils.calendar_range(
            args.calendar_mode, args.assessment_year
        )
        sales: t.List[AssetSale] = []
        for sale_source_parser in SALE_SOURCE_PARSERS[args.source_mode]:
            sales.extend(
                sale_source_parser.parse(
                    args.input_excel_file, time_bounds=time_bounds
                )
            )
        # a report covers a single schedule CG section, so the sales are split by
        # section and each section gets its own file
        for section_type in dict.fromkeys(sale.section_type for sale in sales):
            asset_aggregator.parse(
                [sale for sale in sales if sale.section_type == section_type],
                args.output_folder,
            )
        return

    if args.source_mode == ETRADE_HOLDINGS_BYSTATUS_SOURCE_MODE:
        purchases = etrade_holdings_bystatus_parser.parse(
            args.input_excel_file, args.output_folder
        )
    else:
        purchases = etrade_benefit_history_parser.parse(
            args.input_excel_file,
            args.output_folder,
            time_bounds=(
                None,
                date_utils.calendar_range("calendar", args.assessment_year)[1],
            ),
        )

    faa3_parser.parse(
        args.calendar_mode, purchases, args.assessment_year, args.output_folder
    )


def refresh_historic_data():
    """Best-effort refresh of historic share prices and RBI/FBIL reference rates
    for every configured ticker. Failures (missing dependency, no network) are
    logged and ignored so the run falls back to the bundled historic_data."""
    end = (date.today() + timedelta(days=1)).isoformat()
    tickers = sorted(ticker_org_info)
    for ticker in tickers:
        try:
            refresh(ticker, DEFAULT_START, end)
        except SystemExit as err:
            logger.log(
                f"Skipping share price refresh for {ticker} ({err}); using bundled "
                "historic data. Pass --skip-refresh to suppress this."
            )
        except Exception as err:
            logger.log(
                f"Could not refresh share prices for {ticker} ({err}); "
                "using bundled historic data."
            )

    currencies = sorted(
        {ticker_currency_info[ticker] for ticker in tickers if ticker in ticker_currency_info}
    )
    if currencies:
        try:
            refresh_rbi_rates.refresh(
                currencies, refresh_rbi_rates.DEFAULT_START, date.today().isoformat()
            )
        except SystemExit as err:
            logger.log(
                f"Skipping reference rate refresh ({err}); using bundled rates. "
                "Pass --skip-refresh to suppress this."
            )
        except Exception as err:
            logger.log(
                f"Could not refresh reference rates ({err}); using bundled rates."
            )


if __name__ == "__main__":
    try:
        main()
        logger.log("On your left!")
    except KeyboardInterrupt:
        logger.log("Interrupt requested... exiting")
    sys.exit(0)
