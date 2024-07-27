import pytest
from parser.demat.etrade import etrade_benefit_history_parser
from unittest.mock import MagicMock
import pandas as pd


def create_rsu_mock(data_frame_obj) -> MagicMock:
    mock_excel_file = MagicMock(spec=pd.ExcelFile)
    mock_excel_file.parse.return_value = pd.DataFrame(data_frame_obj)
    mock_excel_file.sheet_names = [etrade_benefit_history_parser.RSU_SHEET_NAME]
    return mock_excel_file


@pytest.fixture(name="benefit_history_excel_file_with_vested_rsu")
def fixture_benefit_history_excel_file_with_vested_rsu():
    return create_rsu_mock(
        {
            "Record Type": ["Grant", "Event"],
            "Symbol": ["ADBE", None],
            "Event Type": [None, "Shares vested"],
        }
    )


@pytest.fixture(name="benefit_history_excel_file_with_vested_and_released_rsu")
def fixture_benefit_history_excel_file_with_vested_and_released_rsu():
    return create_rsu_mock(
        {
            "Record Type": ["Grant", "Event", "Event"],
            "Symbol": ["ADBE", "", ""],
            "Event Type": ["", "Shares vested", "Shares released"],
            "Date": ["", "10/15/2023", "10/15/2023"],
            "Qty. or Amount": [None, 0.5, 0.5],
        }
    )


def test_rsu_parsing_with_only_vest(
    benefit_history_excel_file_with_vested_rsu: pd.ExcelFile,
):
    rsu_purchase = etrade_benefit_history_parser.parse_rsu(
        benefit_history_excel_file_with_vested_rsu
    )
    assert len(rsu_purchase) == 0


def test_rsu_parsing_with_only_released_shares(
    benefit_history_excel_file_with_vested_and_released_rsu: pd.ExcelFile,
):
    rsu_purchases = etrade_benefit_history_parser.parse_rsu(
        benefit_history_excel_file_with_vested_and_released_rsu
    )
    assert len(rsu_purchases) == 1
    rsu_purchase = rsu_purchases[0]
    assert rsu_purchase.quantity == 0.5
    assert rsu_purchase.ticker == "adbe"
    assert rsu_purchase.date == {
        "disp_time": "15-Oct-2023",
        "orig_disp_time": "10/15/2023",
        "time_in_millis": 1697328000000,
    }


def test_wrong_rsu_sheet_without_grant():
    rsu_sheet = create_rsu_mock(
        {
            "Record Type": ["Event", "Event"],
            "Symbol": ["ADBE", ""],
            "Event Type": ["Shares vested", "Shares released"],
            "Date": ["10/15/2023", "10/15/2023"],
            "Qty. or Amount": [0.5, 0.5],
        }
    )
    with pytest.raises(AssertionError) as error:
        etrade_benefit_history_parser.parse_rsu(rsu_sheet)
    assert (
        "There is RSU event without Grant event(which contains the ticker info) "
        + "hence no ticker info is found while parsing Restricted Stock"
        in str(error.value)
    )


def test_rsu_row_without_no_released_share():
    rsu_purchase = etrade_benefit_history_parser.parse_rsu_row(
        {"Event Type": "Random event type"}, "ADBE"
    )
    assert rsu_purchase is None


def test_rsu_row_with_released_share():
    rsu_purchase = etrade_benefit_history_parser.parse_rsu_row(
        {
            "Record Type": "Event",
            "Symbol": "",
            "Event Type": "Shares released",
            "Date": "10/15/2023",
            "Qty. or Amount": 0.5,
        },
        "ADBE",
    )

    assert rsu_purchase is not None
    assert rsu_purchase.quantity == 0.5
