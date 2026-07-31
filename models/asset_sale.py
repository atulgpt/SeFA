from dataclasses import dataclass
import enum
import typing as t

from models.transaction import Price, Transaction

# SBI/FBIL reference rate of the last day of the month preceding the transaction
# month, as required by Rule 115 of the Income-tax Rules, 1962
CalcMethod = t.Literal["sbi_prev_mon_last_day", "not_applicable"]
SBI_PREV_MON_LAST_DAY: CalcMethod = "sbi_prev_mon_last_day"
# the asset is traded in the reporting currency, so no conversion takes place
NOT_APPLICABLE: CalcMethod = "not_applicable"

class SectionType(enum.StrEnum):
    """
    Schedule CG section the sale leg is reported under. STT paid listed Indian
    equity shares and equity oriented mutual funds fall under section 111A when
    short term and section 112A when long term, everything else being taxed at the
    slab rate.
    """

    SECTION_111A = "111A_short"
    SECTION_112A = "112A_long"
    SECTION_SLAB_SHORT = "slab_short"
    SECTION_SLAB_LONG = "slab_long"


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
