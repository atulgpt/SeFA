from dataclasses import dataclass
from models.org import Organization
from models.transaction import TransactionWithTicker


@dataclass
class FAA3:
    org: Organization
    purchase: TransactionWithTicker
    purchase_price: float
    peak_price: float
    closing_price: float
