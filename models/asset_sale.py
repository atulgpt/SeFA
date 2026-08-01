from dataclasses import dataclass
import typing as t

from models.section_type import SectionType
from models.transaction import Price, Transaction

# SBI/FBIL reference rate of the last day of the month preceding the transaction
# month, as required by Rule 115 of the Income-tax Rules, 1962
CalcMethod = t.Literal["sbi_prev_mon_last_day", "not_applicable"]
SBI_PREV_MON_LAST_DAY: CalcMethod = "sbi_prev_mon_last_day"
# the asset is traded in the reporting currency, so no conversion takes place
NOT_APPLICABLE: CalcMethod = "not_applicable"


@dataclass
class AssetSale:
    """
    A single realized sale leg. Both transactions carry the per unit value in the
    currency the asset was traded in, while `expense_exempted` and `gains` carry
    the reporting currency. An exchange rate is None when the source does not
    apply one to that leg
    """

    asset_description: str
    broker: str
    section_type: SectionType
    sale_transaction: Transaction
    purchase_transaction: Transaction
    expense_original: Price
    expense_exempted: Price
    gains: Price
    sale_exchange_rate: t.Optional[float]
    sale_calc_method: CalcMethod
    purchase_exchange_rate: t.Optional[float]
    purchase_calc_method: CalcMethod
    # only the sources that state it fill these in, both being needed to report a
    # holding acquired on or before 31-Jan-2018 under schedule 112A
    isin: t.Optional[str] = None
    fmv_31_jan_2018: t.Optional[Price] = None
