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
from models.section_type import SectionType
from models.section_data import SectionDataMap
from parser.itr import faa3_parser
from aggregator import asset_aggregator
from utils.ticker_mapping import ticker_currency_info, ticker_org_info
from refresh_historic_data import refresh, DEFAULT_START
import refresh_rbi_rates

# arguments defaults
script_path = os.path.realpath(os.path.dirname(__file__))
DEFAULT_OUTPUT_FOLDER_NAME = "output"
default_output_folder_abs_path = os.path.join(script_path, DEFAULT_OUTPUT_FOLDER_NAME)
ETRADE_BENEFIT_HISTORY_OPERATION_MODE = "etrade_benefit_history"
ETRADE_HOLDINGS_BYSTATUS_OPERATION_MODE = "etrade_holdings_bystatus"
INDMONEY_US_STOCKS_OPERATION_MODE = "indmoney_us_stocks"
GROWW_INDIAN_STOCKS_OPERATION_MODE = "groww_indian_stocks"
GROWW_INDIAN_MF_OPERATION_MODE = "groww_indian_mf"

# Operation modes reporting realized sales, which schedule FA under section A3 does
# not consume. A mode lists every parser that reads a table out of that source's
# report, their sales being aggregated together
SALE_OPERATION_PARSERS = {
    INDMONEY_US_STOCKS_OPERATION_MODE: (indmoney_us_stocks_parser,),
    GROWW_INDIAN_STOCKS_OPERATION_MODE: (groww_indian_stocks_parser,),
    GROWW_INDIAN_MF_OPERATION_MODE: (groww_indian_mf_parser,),
}

OPERATION_MODES = [
    ETRADE_BENEFIT_HISTORY_OPERATION_MODE,
    ETRADE_HOLDINGS_BYSTATUS_OPERATION_MODE,
    *SALE_OPERATION_PARSERS,
]

# an input is given as `<operation mode>:<file path>`, which is what lets one run read
# a report per source instead of a single file of a single mode
INPUT_SEPARATOR = ":"

DEFAULT_CALENDER_MODE = "calendar"
FINANCIAL_CALENDER_MODE = "financial"
CALENDER_MODES = [
    DEFAULT_CALENDER_MODE,
    FINANCIAL_CALENDER_MODE,
]


def __parse_inputs(inputs: t.List[str]) -> t.List[t.Tuple[str, str]]:
    """
    Splits every `<operation mode>:<file path>` input into its pair. The same
    operation mode may be repeated when a source is split across more than one file
    """
    parsed_inputs: t.List[t.Tuple[str, str]] = []
    for value in inputs:
        operation_mode, separator, input_excel_file = value.partition(INPUT_SEPARATOR)
        assert separator != "" and input_excel_file != "", (
            f"Input {value} is not of the form"
            f" <operation mode>{INPUT_SEPARATOR}<absolute path of the input Excel file>"
        )
        assert operation_mode in OPERATION_MODES, (
            f"Input {value} carries the unsupported operation mode {operation_mode}."
            f" Supported operation modes = {OPERATION_MODES}"
        )
        parsed_inputs.append((operation_mode, input_excel_file))
    return parsed_inputs


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
        nargs="+",
        dest="inputs",
        metavar=f"OPERATION_MODE{INPUT_SEPARATOR}INPUT_EXCEL_FILE",
        help="Specify one or more"
        f" <operation mode>{INPUT_SEPARATOR}<absolute path of the input Excel file>"
        f" pairs, the supported operation modes being {', '.join(OPERATION_MODES)}. The"
        f" expected report is the benefit history(BenefitHistory.xlsx) for"
        f" {ETRADE_BENEFIT_HISTORY_OPERATION_MODE}, the holdings by status for"
        f" {ETRADE_HOLDINGS_BYSTATUS_OPERATION_MODE}, the consolidated tax report for"
        f" {INDMONEY_US_STOCKS_OPERATION_MODE} and the stocks/mutual funds capital"
        " gains statement for"
        f" {GROWW_INDIAN_STOCKS_OPERATION_MODE}/{GROWW_INDIAN_MF_OPERATION_MODE}."
        f" {', '.join(SALE_OPERATION_PARSERS)} report realized sales and do not feed"
        " the schedule FA generation",
        required=True,
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
    for sale_operation_parsers in SALE_OPERATION_PARSERS.values():
        for sale_operation_parser in sale_operation_parsers:
            sale_operation_parser.DEBUG = args.debug
    asset_aggregator.DEBUG = args.debug

    # Refresh before parsing: RSU rows resolve their FMV from the share price CSV
    # during parsing, so the historic data must be up to date beforehand.
    if not args.skip_refresh:
        refresh_historic_data()

    time_bounds = date_utils.calendar_range(args.calendar_mode, args.assessment_year)

    # every parser hands back its rows keyed by the section they are filed under, so
    # a run is the merge of everything its inputs produced
    sections: SectionDataMap = {}

    def collect(parsed: SectionDataMap) -> None:
        for section_type, rows in parsed.items():
            sections.setdefault(section_type, []).extend(rows)

    for operation_mode, input_excel_file in __parse_inputs(args.inputs):
        if operation_mode in SALE_OPERATION_PARSERS:
            for sale_operation_parser in SALE_OPERATION_PARSERS[operation_mode]:
                collect(
                    sale_operation_parser.parse(
                        input_excel_file, time_bounds=time_bounds
                    )
                )
        elif operation_mode == ETRADE_HOLDINGS_BYSTATUS_OPERATION_MODE:
            collect(
                etrade_holdings_bystatus_parser.parse(
                    input_excel_file,
                    args.output_folder,
                    operation_mode,
                    args.calendar_mode,
                    args.assessment_year,
                )
            )
        elif operation_mode == ETRADE_BENEFIT_HISTORY_OPERATION_MODE:
            collect(
                etrade_benefit_history_parser.parse(
                    input_excel_file,
                    args.output_folder,
                    operation_mode,
                    args.calendar_mode,
                    args.assessment_year,
                    time_bounds=(
                        None,
                        date_utils.calendar_range(
                            "calendar", args.assessment_year
                        )[1],
                    ),
                )
            )

    asset_aggregator.parse(sections, args.output_folder)


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
