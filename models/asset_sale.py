from dataclasses import dataclass
import typing as t

from models.transaction import Price, Transaction

# SBI/FBIL reference rate of the last day of the month preceding the transaction
# month, as required by Rule 115 of the Income-tax Rules, 1962
CalcMethod = t.Literal["sbi_prev_mon_last_day", "not_applicable"]
SBI_PREV_MON_LAST_DAY: CalcMethod = "sbi_prev_mon_last_day"
# the asset is traded in the reporting currency, so no conversion takes place
NOT_APPLICABLE: CalcMethod = "not_applicable"

# Schedule CG section the sale leg is reported under. STT paid listed Indian
# equity shares and equity oriented mutual funds fall under section 111A when
# short term and section 112A when long term, everything else is reported under
# the corresponding "other than" section
SectionType = t.Literal["111A", "112A", "other_than_111A", "other_than_112A"]
SECTION_111A: SectionType = "111A"
SECTION_112A: SectionType = "112A"
SECTION_OTHER_THAN_111A: SectionType = "other_than_111A"
SECTION_OTHER_THAN_112A: SectionType = "other_than_112A"


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
