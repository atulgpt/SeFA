import typing as t

import pandas as pd
import pytest

from sefa.aggregator import asset_aggregator
from sefa.models.asset_sale import NOT_APPLICABLE, AssetSale
from sefa.models.section_data import SectionDataMap, SectionDataRow
from sefa.models.section_type import SectionType
from sefa.models.transaction import Price, Transaction
from sefa.utils import date_utils

# every leg is traded in the reporting currency, so no exchange rate is looked up and
# the figures the sheets state are the ones the sales carry
REPORTING_CURRENCY_CODE = "INR"

QUARTER_LABELS = [label for label, _ in asset_aggregator.QUARTERS]

# one sale date inside each quarter of schedule CG table F, in quarter order
QUARTER_SALE_DATES = (
    "2023-05-10",
    "2023-08-20",
    "2023-11-05",
    "2024-02-14",
    "2024-03-20",
)

# every sale is one unit bought and expensed for the same amount, so its gain is the
# only figure that varies between them
TEST_PURCHASE_PRICE_PER_UNIT = 1000.0
TEST_EXPENSE = 10.0

# a sale carries these whatever section it is filed under, so they are fixed rather
# than stated per sale. The ISIN and the 31-Jan-2018 value are read only for the
# holdings schedule 112A grandfathers, which assert on both being present
TEST_ASSET_DESCRIPTION = "test asset description"
TEST_BROKER = "test_broker"
TEST_ISIN = "INE000A01001"
TEST_FMV_31_JAN_2018 = 900.0


def build_sale(
    section_type: SectionType,
    sale_date: str,
    purchase_date: str,
    gain: float,
) -> AssetSale:
    """
    A one unit sale gaining exactly `gain`, its sale price being the cost and the
    expense marked up by that gain
    """
    sale_transaction = Transaction(
        date=date_utils.parse_yyyy_mm_dd(sale_date),
        fmv=Price(
            TEST_PURCHASE_PRICE_PER_UNIT + TEST_EXPENSE + gain, REPORTING_CURRENCY_CODE
        ),
        quantity=1,
    )
    purchase_transaction = Transaction(
        date=date_utils.parse_yyyy_mm_dd(purchase_date),
        fmv=Price(TEST_PURCHASE_PRICE_PER_UNIT, REPORTING_CURRENCY_CODE),
        quantity=1,
    )
    return AssetSale(
        asset_description=TEST_ASSET_DESCRIPTION,
        broker=TEST_BROKER,
        section_type=section_type,
        sale_transaction=sale_transaction,
        purchase_transaction=purchase_transaction,
        expense_original=Price(TEST_EXPENSE, REPORTING_CURRENCY_CODE),
        expense_exempted=Price(TEST_EXPENSE, REPORTING_CURRENCY_CODE),
        gains=Price(gain, REPORTING_CURRENCY_CODE),
        sale_exchange_rate=None,
        sale_calc_method=NOT_APPLICABLE,
        purchase_exchange_rate=None,
        purchase_calc_method=NOT_APPLICABLE,
        isin=TEST_ISIN,
        fmv_31_jan_2018=Price(TEST_FMV_31_JAN_2018, REPORTING_CURRENCY_CODE),
    )


def build_section_sales(
    section_type: SectionType,
    quarter_gains: t.Sequence[float],
    purchase_dates: t.Tuple[str, ...],
) -> t.List[SectionDataRow]:
    """
    One sale per quarter, the sale sitting in quarter `n` gaining `quarter_gains[n]`
    """
    return [
        build_sale(
            section_type=section_type,
            sale_date=sale_date,
            purchase_date=purchase_date,
            gain=gain,
        )
        for sale_date, purchase_date, gain in zip(
            QUARTER_SALE_DATES, purchase_dates, quarter_gains
        )
    ]


TEST_SECTION_111A_QUARTER_GAINS = [100, 200, 300, 400, 500]
TEST_SECTION_112A_QUARTER_GAINS = [600, 700, 800, 900, 1000]
TEST_SECTION_SLAB_SHORT_QUARTER_GAINS = [1100, 1200, 1300, 1400, 1500]

# a section states the cost and the expense of its five sales, plus their gains
TEST_SECTION_COST_OF_ACQUISITION = int(5 * TEST_PURCHASE_PRICE_PER_UNIT)
TEST_SECTION_TRANSFER_EXPENDITURE = int(5 * TEST_EXPENSE)


def full_value_of_consideration(quarter_gains: t.List[int]) -> int:
    return (
        TEST_SECTION_COST_OF_ACQUISITION
        + TEST_SECTION_TRANSFER_EXPENDITURE
        + sum(quarter_gains)
    )


@pytest.fixture(name="capital_gain_summary_output_file_path")
def fixture_capital_gain_summary(tmp_path) -> str:
    """
    The workbook written for a run holding a sale in every quarter of each of the
    three sections
    """
    sections = SectionDataMap(
        {
            SectionType.SECTION_111A: build_section_sales(
                SectionType.SECTION_111A,
                quarter_gains=TEST_SECTION_111A_QUARTER_GAINS,
                purchase_dates=("2023-01-05",) * len(QUARTER_SALE_DATES),
            ),
            # the first quarter's holding was bought before the 31-Jan-2018 cutoff, so
            # this section also exercises the grandfathered schedule 112A path
            SectionType.SECTION_112A: build_section_sales(
                SectionType.SECTION_112A,
                quarter_gains=TEST_SECTION_112A_QUARTER_GAINS,
                purchase_dates=("2017-06-01",) + ("2020-05-01",) * 4,
            ),
            SectionType.SECTION_SLAB_SHORT: build_section_sales(
                SectionType.SECTION_SLAB_SHORT,
                quarter_gains=TEST_SECTION_SLAB_SHORT_QUARTER_GAINS,
                purchase_dates=("2023-01-10",) * len(QUARTER_SALE_DATES),
            ),
        }
    )

    asset_aggregator.parse(sections, str(tmp_path))
    return str(tmp_path / asset_aggregator.CAPITAL_GAIN_SUMMARY_OUTPUT_FILE_NAME)


def test_summary_sheet_is_the_first_sheet_of_the_workbook(
    capital_gain_summary_output_file_path: str,
):
    with pd.ExcelFile(capital_gain_summary_output_file_path) as xl:
        assert xl.sheet_names == [
            asset_aggregator.SUMMARY_OUTPUT_SHEET_NAME,
            SectionType.SECTION_111A,
            SectionType.SECTION_112A,
            SectionType.SECTION_SLAB_SHORT,
        ]


@pytest.mark.parametrize(
    ("section_type", "quarter_gains"),
    [
        (SectionType.SECTION_111A, TEST_SECTION_111A_QUARTER_GAINS),
        (SectionType.SECTION_112A, TEST_SECTION_112A_QUARTER_GAINS),
        (SectionType.SECTION_SLAB_SHORT, TEST_SECTION_SLAB_SHORT_QUARTER_GAINS),
    ],
)
def test_summary_sheet_states_the_schedule_cg_totals_of_every_section(
    capital_gain_summary_output_file_path: str,
    section_type: SectionType,
    quarter_gains: t.List[int],
):
    summary = pd.read_excel(
        capital_gain_summary_output_file_path,
        sheet_name=asset_aggregator.SUMMARY_OUTPUT_SHEET_NAME,
    )
    assert list(summary.columns) == [
        asset_aggregator.SECTION_COLUMN,
        asset_aggregator.FULL_VALUE_OF_CONSIDERATION_LABEL,
        asset_aggregator.COST_OF_ACQUISITION_LABEL,
        asset_aggregator.TRANSFER_EXPENDITURE_LABEL,
    ]

    row = summary.set_index(asset_aggregator.SECTION_COLUMN).loc[section_type]
    assert row[
        asset_aggregator.FULL_VALUE_OF_CONSIDERATION_LABEL
    ] == full_value_of_consideration(quarter_gains)
    assert (
        row[asset_aggregator.COST_OF_ACQUISITION_LABEL]
        == TEST_SECTION_COST_OF_ACQUISITION
    )
    assert (
        row[asset_aggregator.TRANSFER_EXPENDITURE_LABEL]
        == TEST_SECTION_TRANSFER_EXPENDITURE
    )


@pytest.mark.parametrize(
    ("section_type", "quarter_gains"),
    [
        (SectionType.SECTION_111A, TEST_SECTION_111A_QUARTER_GAINS),
        (SectionType.SECTION_112A, TEST_SECTION_112A_QUARTER_GAINS),
        (SectionType.SECTION_SLAB_SHORT, TEST_SECTION_SLAB_SHORT_QUARTER_GAINS),
    ],
)
def test_every_section_breaks_its_gain_up_quarter_wise(
    capital_gain_summary_output_file_path: str,
    section_type: SectionType,
    quarter_gains: t.List[int],
):
    quarters = pd.read_excel(
        capital_gain_summary_output_file_path, sheet_name=section_type
    )
    assert list(quarters.columns) == (
        [asset_aggregator.SECTION_COLUMN]
        + QUARTER_LABELS
        + [asset_aggregator.TOTAL_COLUMN]
    )

    assert len(quarters) == 1
    row = quarters.iloc[0]
    assert row[asset_aggregator.SECTION_COLUMN] == section_type
    assert list(row[QUARTER_LABELS]) == quarter_gains
    # the quarters add back to the gain the summary row itself states
    assert row[asset_aggregator.TOTAL_COLUMN] == sum(quarter_gains)


def write_single_section_summary(tmp_path, quarter_gains: t.List[float]) -> str:
    """
    The workbook of a run holding one section only, its sales gaining `quarter_gains`
    quarter by quarter. A quarter past the end of the list holds no sale at all
    """
    asset_aggregator.parse(
        SectionDataMap(
            {
                SectionType.SECTION_111A: build_section_sales(
                    SectionType.SECTION_111A,
                    quarter_gains=quarter_gains,
                    purchase_dates=("2023-01-05",) * len(QUARTER_SALE_DATES),
                )
            }
        ),
        str(tmp_path),
    )
    return str(tmp_path / asset_aggregator.CAPITAL_GAIN_SUMMARY_OUTPUT_FILE_NAME)


@pytest.mark.parametrize(
    ("quarter_gains", "expected_quarter_gains"),
    [
        ([0, 100, -200, 200], [0, 100, 0, 0, 0]),
        ([0, 400, -300, 200], [0, 300, 0, 0, 0]),
        ([100.5, 100.4, 100.1, 0], [100, 100, 101, 0, 0]),
    ],
)
def test_quarter_wise_breakup_holds_whole_non_negative_quarters(
    tmp_path,
    quarter_gains: t.List[float],
    expected_quarter_gains: t.List[int],
):
    summary_output_file_path = write_single_section_summary(tmp_path, quarter_gains)

    quarters = pd.read_excel(
        summary_output_file_path, sheet_name=SectionType.SECTION_111A
    )
    row = quarters.iloc[0]
    assert list(row[QUARTER_LABELS]) == expected_quarter_gains
    assert row[asset_aggregator.TOTAL_COLUMN] == sum(expected_quarter_gains)

    summary = pd.read_excel(
        summary_output_file_path,
        sheet_name=asset_aggregator.SUMMARY_OUTPUT_SHEET_NAME,
    )
    summary_row = summary.set_index(asset_aggregator.SECTION_COLUMN).loc[
        SectionType.SECTION_111A
    ]
    # the same gain the summary sheet arrives at from its own totals
    assert (
        summary_row[asset_aggregator.FULL_VALUE_OF_CONSIDERATION_LABEL]
        - summary_row[asset_aggregator.COST_OF_ACQUISITION_LABEL]
        - summary_row[asset_aggregator.TRANSFER_EXPENDITURE_LABEL]
    ) == sum(expected_quarter_gains)


def test_section_running_at_an_overall_loss_has_no_quarter_wise_breakup(tmp_path):
    summary_output_file_path = write_single_section_summary(
        tmp_path, [100, 100, 100, -400]
    )

    with pd.ExcelFile(summary_output_file_path) as xl:
        assert xl.sheet_names == [asset_aggregator.SUMMARY_OUTPUT_SHEET_NAME]
