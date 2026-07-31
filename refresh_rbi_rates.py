#!/usr/bin/env python3
"""Refresh historic_data/rates/rbi/rates.xls from the FBIL reference rate.

The ITR parser (utils/rates/rbi_rates_utils.py) reads a "Reference Rates" sheet
whose header sits on the third row (two title rows above it) with columns
"Date" (%d %b %Y), "Time", "Currency Pairs" (e.g. "INR / 1 USD"), "Rate" and
"Comments". For each month it keeps the latest available date, i.e. the
month-end reference rate.

FBIL took over the spot USD/INR reference rate from the RBI on 2018-07-10, so
data is only available from that date. The rates are fetched from the public
Frankfurter API (https://frankfurter.dev), which exposes the FBIL benchmark via
`providers=FBIL`. Only the currency pairs that are refreshed are replaced; any
other pairs already in the file (and older RBI-era data) are left untouched.
"""
import argparse
import os
import sys
from datetime import date, datetime

from utils.runtime_utils import warn_missing_module

script_path = os.path.realpath(os.path.dirname(__file__))
RATES_PATH = os.path.join(script_path, "historic_data", "rates", "rbi", "rates.xls")
SHEET_NAME = "Reference Rates"
COLUMNS = ["Date", "Time", "Currency Pairs", "Rate", "Comments"]
TITLE_ROWS = ["Financial Benchmarks India Pvt Ltd", SHEET_NAME]
RATE_TIME = "1:30:00 PM"
DATE_FMT = "%d %b %Y"

DEFAULT_CURRENCIES = ["USD"]
# FBIL began publishing the spot USD/INR reference rate on 2018-07-10.
DEFAULT_START = "2018-07-10"
FRANKFURTER_URL = "https://api.frankfurter.dev/v2/rates"
QUOTE_CURRENCY = "INR"


def __fetch_month_end_rates(currency: str, start: str, end: str):
    """Return an ordered list of (datetime, rate) for the last FBIL business day
    of each month in [start, end), as INR per 1 unit of `currency`."""
    warn_missing_module("requests")
    import requests

    resp = requests.get(
        FRANKFURTER_URL,
        params={
            "from": start,
            "to": end,
            "base": currency,
            "quotes": QUOTE_CURRENCY,
            "providers": "FBIL",
        },
        timeout=60,
    )
    resp.raise_for_status()
    payload = resp.json()
    if isinstance(payload, dict):  # error responses come back as an object
        raise SystemExit(
            f"FBIL fetch for {currency} failed: {payload.get('message', payload)}"
        )

    # payload is ascending by date, so the last entry per month wins.
    month_end = {}
    for entry in payload:
        if entry.get("quote") != QUOTE_CURRENCY:
            continue
        entry_date = datetime.strptime(entry["date"], "%Y-%m-%d")
        month_end[(entry_date.year, entry_date.month)] = (entry_date, entry["rate"])
    return list(month_end.values())


def __read_existing(rates_path: str):
    """Return existing data rows (list of COLUMNS-ordered lists), or [] if the
    file is missing or unreadable."""
    if not os.path.exists(rates_path):
        return []
    warn_missing_module("pandas")
    import pandas as pd

    with pd.ExcelFile(rates_path, engine="openpyxl") as xl:
        df = xl.parse(sheet_name=SHEET_NAME, skiprows=0, header=2)
    df = df.reindex(columns=COLUMNS)
    return [
        [None if pd.isna(value) else value for value in row]
        for row in df.itertuples(index=False)
    ]


def __write(rates_path: str, rows):
    warn_missing_module("openpyxl")
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_NAME
    for title in TITLE_ROWS:
        ws.append([title])
    ws.append(COLUMNS)
    for row in rows:
        ws.append(row)

    # openpyxl refuses to save under a ".xls" name, so write .xlsx bytes to a
    # temp path and move it into place (the parser reads it via pandas anyway).
    tmp_path = rates_path + ".tmp.xlsx"
    wb.save(tmp_path)
    os.replace(tmp_path, rates_path)


def refresh(currencies, start: str, end: str, rates_path: str = RATES_PATH) -> str:
    refreshed_pairs = {f"INR / 1 {cur.upper()}" for cur in currencies}
    # Keep every existing row whose pair we are NOT refreshing.
    rows = [
        row for row in __read_existing(rates_path) if row[2] not in refreshed_pairs
    ]

    added = 0
    for cur in currencies:
        pair = f"INR / 1 {cur.upper()}"
        for entry_date, rate in __fetch_month_end_rates(cur, start, end):
            rows.append([entry_date.strftime(DATE_FMT), RATE_TIME, pair, rate, None])
            added += 1

    os.makedirs(os.path.dirname(rates_path), exist_ok=True)
    __write(rates_path, rows)
    print(
        f"Wrote {len(rows)} rows to {rates_path} "
        f"({added} refreshed for {sorted(refreshed_pairs)})"
    )
    return rates_path


def main():
    parser = argparse.ArgumentParser(
        description="Refresh RBI/FBIL reference rate xls from Frankfurter (FBIL)"
    )
    parser.add_argument(
        "-c",
        "--currency",
        action="append",
        dest="currencies",
        help=f"Currency code to refresh (repeatable), default = {DEFAULT_CURRENCIES}",
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
        default=date.today().isoformat(),
        dest="end",
        help="End date (YYYY-MM-DD, inclusive), default = today",
    )
    args = parser.parse_args()
    refresh(args.currencies or DEFAULT_CURRENCIES, args.start, args.end)


if __name__ == "__main__":
    main()
    sys.exit(0)
