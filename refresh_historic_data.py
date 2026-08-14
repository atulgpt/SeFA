#!/usr/bin/env python3
"""Refresh historic_data/shares/<ticker>/data.csv from Yahoo Finance via yfinance.

The ITR parser (utils/share_data_utils.py) reads a single-header CSV with a
"Date" column in %Y-%m-%d format and a "Close" column. yfinance returns a
MultiIndex column frame whose default to_csv output has extra header rows, so
this script flattens the columns and reformats the date before writing.
"""

import argparse
import os
import sys
from datetime import date, timedelta

from utils.runtime_utils import warn_missing_module

script_path = os.path.realpath(os.path.dirname(__file__))
DEFAULT_TICKER = "adbe"
DEFAULT_START = "1986-08-13"


def refresh(ticker: str, start: str, end: str) -> str:
    # Imported lazily so importing this module (e.g. from run.py) does not
    # require yfinance to be installed unless a refresh is actually requested.
    warn_missing_module("yfinance")
    # pylint: disable-next=import-outside-toplevel
    import yfinance as yf

    df = yf.download(
        ticker.upper(), start=start, end=end, auto_adjust=False, rounding=True
    )
    if df.empty:
        raise SystemExit(f"No data returned from yfinance for ticker {ticker}")

    # yfinance returns MultiIndex columns (field, ticker); drop the ticker level.
    if df.columns.nlevels > 1:
        df.columns = df.columns.droplevel(1)

    df = df.reset_index()
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

    out_path = os.path.join(
        script_path, "historic_data", "shares", ticker.lower(), "data.csv"
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df)} rows for {ticker.lower()} to {out_path}")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refresh historic share price CSV from Yahoo Finance"
    )
    parser.add_argument(
        "-t",
        "--ticker",
        default=DEFAULT_TICKER,
        dest="ticker",
        help=f"Ticker symbol, default = {DEFAULT_TICKER}",
    )
    parser.add_argument(
        "-s",
        "--start",
        default=DEFAULT_START,
        dest="start",
        help=f"Start date (YYYY-MM-DD), default = {DEFAULT_START}",
    )
    parser.add_argument(
        "-e",
        "--end",
        default=(date.today() + timedelta(days=1)).isoformat(),
        dest="end",
        help="End date (YYYY-MM-DD, exclusive), default = tomorrow",
    )
    args = parser.parse_args()
    refresh(args.ticker, args.start, args.end)


if __name__ == "__main__":
    main()
    sys.exit(0)
