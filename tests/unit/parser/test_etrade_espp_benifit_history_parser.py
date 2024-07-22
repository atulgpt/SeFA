import pytest
from parser.demat import etrade_benefit_history_parser
from unittest.mock import MagicMock
import pandas as pd


def create_espp_mock(data_frame_obj) -> MagicMock:
    mock_excel_file = MagicMock(spec=pd.ExcelFile)
    mock_excel_file.parse.return_value = pd.DataFrame(data_frame_obj)
    mock_excel_file.sheet_names = [etrade_benefit_history_parser.ESPP_SHEET_NAME]
    return mock_excel_file


@pytest.fixture(name="benefit_history_excel_file_with_no_purchase_espp")
def fixture_benefit_history_excel_file_with_no_purchase_espp():
    return create_espp_mock(
        {
            "Record Type": [],
            "Symbol": [],
            "Event Type": [],
        }
    )


@pytest.fixture(name="benefit_history_excel_file_with_vested_and_released_espp")
def fixture_benefit_history_excel_file_with_vested_and_released_espp():
    return create_espp_mock(
        {
            "Record Type": ["Purchase", "Event", "Event"],
            "Symbol": ["ADBE", "", ""],
            "Purchase Date": ["30-JUN-2020", "", ""],
            "Sellable Qty.": ["2", None, None],
            "Qty. or Amount": [None, 0.5, 0.5],
            "Purchase Date FMV": ["$435.31", None, None],
        }
    )


def test_espp_parsing_with_no_purchase(
    benefit_history_excel_file_with_no_purchase_espp: pd.ExcelFile,
):
    espp_purchase = etrade_benefit_history_parser.parse_espp(
        benefit_history_excel_file_with_no_purchase_espp
    )
    assert len(espp_purchase) == 0


def test_espp_parsing_row_with_no_purchase():
    espp_purchase = etrade_benefit_history_parser.parse_espp_row(
        pd.Series(
            {
                "Record Type": "Some random type",
            }
        )
    )
    assert espp_purchase is None


def test_espp_parsing_row_with_valid_purchase():
    espp_purchase = etrade_benefit_history_parser.parse_espp_row(
        pd.Series(
            {
                "Record Type": "Purchase",
                "Symbol": "ADBE",
                "Purchase Date": "30-JUN-2020",
                "Sellable Qty.": "2",
                "Purchase Date FMV": "$435.31",
            }
        )
    )
    assert espp_purchase is not None
    assert espp_purchase.quantity == 2.0


def test_espp_parsing_with_only_released_shares(
    benefit_history_excel_file_with_vested_and_released_espp: pd.ExcelFile,
):
    espp_purchases = etrade_benefit_history_parser.parse_espp(
        benefit_history_excel_file_with_vested_and_released_espp
    )
    assert len(espp_purchases) == 1
    espp_purchase = espp_purchases[0]
    assert espp_purchase.quantity == 2
    assert espp_purchase.purchase_fmv.currency_code == "USD"
    assert espp_purchase.purchase_fmv.price == 435.31
    assert espp_purchase.ticker == "adbe"
    assert espp_purchase.date == {
        "disp_time": "30-Jun-2020",
        "orig_disp_time": "30-JUN-2020",
        "time_in_millis": 1593475200000,
    }
