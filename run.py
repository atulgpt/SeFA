#!/usr/bin/env python3
import argparse
import os
import sys
import traceback

from utils import logger
from parser.demat import etrade_benefit_history_parser, etrade_holdings_bystatus_parser
from parser.itr import faa3_parser

# arguments defaults
script_path = os.path.realpath(os.path.dirname(__file__))
default_output_folder_name = "output"
default_output_folder_abs_path = os.path.join(script_path, default_output_folder_name)
default_source_mode = "etrade_benefit_history"
default_calendar_mode = "calendar"


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
        help=f"Specify the absolute path for input benefit history(BenefitHistory.xlsx) Excel file",
        required=True,
    )
    parser.add_argument(
        "-m",
        "--source-mode",
        action="store",
        default=default_source_mode,
        dest="source_mode",
        choices=[f"{default_source_mode}", "etrade_holdings_bystatus"],
        help=f"Specify the source mode, default = {default_source_mode}",
    )
    parser.add_argument(
        "-cal",
        "--calendar-mode",
        action="store",
        type=str,
        default=default_calendar_mode,
        dest="calendar_mode",
        choices=[f"{default_calendar_mode}", "financial"],
        help=f"Specify the calendar period for consideration, default = {default_calendar_mode}",
    )
    parser.add_argument(
        "-ay",
        "--assessment-year",
        action="store",
        dest="assessment_year",
        type=int,
        required=True,
        help=f"Current year of assessment year. For AY 2019-2020, input will be 2019. Input will be of type integer",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        dest="debug",
        default=False,
        help="Enable the debug logs",
    )

    args = parser.parse_args()

    logger.debug = args.debug
    etrade_benefit_history_parser.debug = args.debug
    etrade_holdings_bystatus_parser.debug = args.debug

    if args.source_mode == "etrade_holdings_bystatus":
        purchases = etrade_holdings_bystatus_parser.parse(
            args.input_excel_file, args.output_folder
        )
    else:
        purchases = etrade_benefit_history_parser.parse(
            args.input_excel_file, args.output_folder
        )

    faa3_parser.parse(
        args.calendar_mode, purchases, args.assessment_year, args.output_folder
    )


if __name__ == "__main__":
    try:
        main()
        logger.log("On your left!")
    except KeyboardInterrupt:
        logger.log("Interrupt requested... exiting")
    except Exception:
        traceback.print_exc(file=sys.stdout)
    sys.exit(0)
