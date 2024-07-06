from dataclasses import dataclass
from org import Organization
from purchase import Purchase


@dataclass
class FAA3:
    org: Organization
    purchase: Purchase
    purchase_price: float
    peak_price: float
    closing_price: float
