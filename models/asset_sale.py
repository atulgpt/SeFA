from dataclasses import dataclass
import typing as t

from models.transaction import Price, Transaction

# SBI/FBIL reference rate of the last day of the month preceding the transaction
# month, as required by Rule 115 of the Income-tax Rules, 1962
CalcMethod = t.Literal["sbi_prev_mon_last_day"]
SBI_PREV_MON_LAST_DAY: CalcMethod = "sbi_prev_mon_last_day"


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
    sale_transaction: Transaction
    purchase_transaction: Transaction
    expense_original: Price
    expense_exempted: Price
    gains: Price
    sale_exchange_rate: t.Optional[float]
    sale_calc_method: CalcMethod
    purchase_exchange_rate: t.Optional[float]
    purchase_calc_method: CalcMethod
