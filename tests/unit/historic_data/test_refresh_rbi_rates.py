import typing as t

import pandas as pd
import pytest
import requests
from openpyxl import Workbook

from sefa.historic_data.rates.rbi import refresh_rbi_rates
from sefa.utils.rates.constants import RATES_SHEET_NAME

# Shape of the keyless AllRatesToday RBI table, trimmed to the fields read
TEST_ALLRATESTODAY_PAYLOAD: t.Dict[str, t.Any] = {
    "bank": "rbi",
    "rate_date": "2026-10-30",
    "rates": [
        {"base": "EUR", "quote": "INR", "type": "reference", "value": 106.5451},
        {"base": "USD", "quote": "INR", "type": "reference", "value": 95.2492},
    ],
}

# Frankfurter v2 rows for Oct 2026, ascending by date
TEST_FRANKFURTER_PAYLOAD: t.List[t.Dict[str, t.Any]] = [
    {"date": "2026-10-29", "base": "USD", "quote": "INR", "rate": 95.1},
    {"date": "2026-10-30", "base": "USD", "quote": "INR", "rate": 95.2},
]

TEST_EXISTING_ROWS: t.List[t.List[t.Any]] = [
    ["30 Sep 2026", "1:30:00 PM", "INR / 1 USD", 94.0, None],
    ["15 Oct 2026", "1:30:00 PM", "INR / 1 USD", 94.5, None],
    ["30 Sep 2026", "1:30:00 PM", "INR / 1 EUR", 104.0, None],
]


class FakeResponse:
    def __init__(self, payload: t.Any) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> t.Any:
        return self.payload


@pytest.fixture(name="rates_path")
def fixture_rates_path(tmp_path):
    path = tmp_path / "rates.xlsx"
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = RATES_SHEET_NAME
    for title in refresh_rbi_rates.TITLE_ROWS:
        ws.append([title])
    ws.append(refresh_rbi_rates.COLUMNS)
    for row in TEST_EXISTING_ROWS:
        ws.append(row)
    wb.save(path)
    return str(path)


def fake_get(frankfurter: t.Any, calls: t.List[str]) -> t.Callable[..., FakeResponse]:
    def get(url: str, **_kwargs: t.Any) -> FakeResponse:
        calls.append(url)
        if url == refresh_rbi_rates.ALLRATESTODAY_RBI_URL:
            return FakeResponse(TEST_ALLRATESTODAY_PAYLOAD)
        if isinstance(frankfurter, Exception):
            raise frankfurter
        return FakeResponse(frankfurter)

    return get


def read_rows(rates_path: str) -> t.List[t.Tuple[str, str, float]]:
    with pd.ExcelFile(rates_path, engine="openpyxl") as xl:
        df = xl.parse(sheet_name=RATES_SHEET_NAME, header=2)
    return sorted(
        (row["Currency Pairs"], row["Date"], row["Rate"]) for _, row in df.iterrows()
    )


def test_frankfurter_is_used_when_reachable(monkeypatch, rates_path):
    calls: t.List[str] = []
    monkeypatch.setattr(requests, "get", fake_get(TEST_FRANKFURTER_PAYLOAD, calls))
    refresh_rbi_rates.refresh(["USD"], "2026-10-01", "2026-10-31", rates_path)

    assert calls == [refresh_rbi_rates.FRANKFURTER_URL]
    assert read_rows(rates_path) == [
        ("INR / 1 EUR", "30 Sep 2026", 104.0),
        ("INR / 1 USD", "30 Oct 2026", 95.2),
    ]


@pytest.mark.parametrize(
    "frankfurter",
    [requests.ConnectionError("down"), {"message": "provider unavailable"}],
)
def test_latest_month_falls_back_to_allratestoday(monkeypatch, rates_path, frankfurter):
    calls: t.List[str] = []
    monkeypatch.setattr(requests, "get", fake_get(frankfurter, calls))
    refresh_rbi_rates.refresh(["USD"], "2018-07-10", "2026-10-31", rates_path)

    assert calls == [
        refresh_rbi_rates.FRANKFURTER_URL,
        refresh_rbi_rates.ALLRATESTODAY_RBI_URL,
    ]
    # September keeps its row, October's row is replaced by the latest rate
    assert read_rows(rates_path) == [
        ("INR / 1 EUR", "30 Sep 2026", 104.0),
        ("INR / 1 USD", "30 Oct 2026", 95.2492),
        ("INR / 1 USD", "30 Sep 2026", 94.0),
    ]


def test_fallback_without_the_currency_fails(monkeypatch, rates_path):
    monkeypatch.setattr(
        requests,
        "get",
        fake_get(requests.ConnectionError("down"), []),
    )
    with pytest.raises(SystemExit, match="no CAD/INR rate"):
        refresh_rbi_rates.refresh(["CAD"], "2018-07-10", "2026-10-31", rates_path)


def test_fallback_outside_the_range_reraises(monkeypatch, rates_path):
    monkeypatch.setattr(
        requests,
        "get",
        fake_get(requests.ConnectionError("down"), []),
    )
    with pytest.raises(requests.ConnectionError):
        refresh_rbi_rates.refresh(["USD"], "2018-07-10", "2025-12-31", rates_path)
