from dataclasses import dataclass

from models.org import Organization
from utils.date_utils import DateObj


@dataclass
class FAA3:
    """
    One schedule FA section A3 row, every figure already in the reporting currency
    """

    org: Organization
    purchase_date: DateObj
    purchase_price: float
    peak_price: float
    closing_price: float
    # a source that does not state them leaves them at zero
    gross_amount_paid: float = 0.0
    gross_sale_proceeds: float = 0.0
