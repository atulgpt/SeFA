from parser.demat.etrade import etrade_benefit_history_parser
import pandas as pd

from utils import date_utils


def test_espp_parsing_with_no_purchase(
    benefit_history_excel_file_with_no_purchase_espp: pd.ExcelFile,
    time_bounds_in_ms: date_utils.DateBoundsInMs,
):
    espp_purchase = etrade_benefit_history_parser.parse_espp(
        benefit_history_excel_file_with_no_purchase_espp, time_bounds_in_ms
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
                "Purchased Qty.": "3",
                "Net Shares": "2",
                "Sellable Qty.": "2",
                "Purchase Date FMV": "$435.31",
            }
        )
    )
    assert espp_purchase is not None
    assert espp_purchase.purchase.quantity == 2.0


def test_espp_parsing_row_with_fully_sold_purchase():
    # Purchased Qty. is the amount originally bought; Sellable Qty. can have
    # since dropped to 0 if all of it was sold - quantity must still reflect
    # the original purchase, not the now-empty sellable balance.
    espp_purchase = etrade_benefit_history_parser.parse_espp_row(
        pd.Series(
            {
                "Record Type": "Purchase",
                "Symbol": "ADBE",
                "Purchase Date": "30-JUN-2016",
                "Purchased Qty.": "5",
                "Net Shares": "5",
                "Sellable Qty.": "0",
                "Purchase Date FMV": "$100.00",
            }
        )
    )
    assert espp_purchase is not None
    assert espp_purchase.purchase.quantity == 5.0


def test_espp_parsing_row_excludes_tax_collection_shares():
    # Regression test: "Purchased Qty." is gross - some of it ("Tax
    # Collection Shares") is withheld to cover tax on the ESPP discount and
    # never actually held by the taxpayer. quantity must reflect "Net
    # Shares" (Purchased Qty. - Tax Collection Shares), not the gross figure,
    # same principle as RSU's "Shares released" (net) vs "Shares vested"
    # (gross).
    espp_purchase = etrade_benefit_history_parser.parse_espp_row(
        pd.Series(
            {
                "Record Type": "Purchase",
                "Symbol": "ADBE",
                "Purchase Date": "30-DEC-2022",
                "Purchased Qty.": "22.628",
                "Tax Collection Shares": "1",
                "Net Shares": "21.628",
                "Sellable Qty.": "11.628",
                "Purchase Date FMV": "$336.53",
            }
        )
    )
    assert espp_purchase is not None
    assert espp_purchase.purchase.quantity == 21.628


def test_espp_parsing_with_only_released_shares(
    benefit_history_excel_file_with_vested_and_released_espp: pd.ExcelFile,
    time_bounds_in_ms: date_utils.DateBoundsInMs,
):
    espp_purchases = etrade_benefit_history_parser.parse_espp(
        benefit_history_excel_file_with_vested_and_released_espp,
        time_bounds_in_ms=time_bounds_in_ms,
    )
    assert len(espp_purchases) == 1
    espp_purchase = espp_purchases[0]
    assert espp_purchase.purchase.quantity == 2
    assert espp_purchase.purchase.fmv.currency_code == "USD"
    assert espp_purchase.purchase.fmv.price == 435.31
    assert espp_purchase.ticker == "adbe"
    assert espp_purchase.purchase.date == {
        "disp_time": "30-Jun-2020",
        "orig_disp_time": "30-JUN-2020",
        "time_in_millis": 1593475200000,
    }
