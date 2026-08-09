from unittest.mock import patch
import pytest

from parser.demat.etrade import etrade_benefit_history_parser
from utils import date_utils


@patch("pandas.read_excel")
@pytest.mark.skip(
    reason="need to abstract out the ExcelFile creation for \
        testing o/w it gives File not found error"
)
def test_returns_correct_purchases_summing_espp_and_rsu(
    mock_read_excel,
    benefit_history_excel_file_with_vested_and_released_espp,
    benefit_history_excel_file_with_vested_and_released_rsu,
    time_bounds_in_ms: date_utils.DateBoundsInMs,
):
    # Create mock DataFrames
    mock_sheet1 = benefit_history_excel_file_with_vested_and_released_espp

    mock_sheet2 = benefit_history_excel_file_with_vested_and_released_rsu

    # Configure the mock to return a dictionary of DataFrames
    mock_read_excel.return_value = {
        etrade_benefit_history_parser.ESPP_SHEET_NAME: mock_sheet1,
        etrade_benefit_history_parser.RSU_SHEET_NAME: mock_sheet2,
    }
    etrade_benefit_history_parser.parse(
        "", "", "benefit_history", "calendar", 2024, time_bounds_in_ms
    )


def test_wrong_file_path_raises_file_not_found_error(
    time_bounds_in_ms: date_utils.DateBoundsInMs,
):
    with pytest.raises(FileNotFoundError):
        etrade_benefit_history_parser.parse(
            "", "", "benefit_history", "calendar", 2024, time_bounds_in_ms
        )
