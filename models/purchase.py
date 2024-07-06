from dataclasses import dataclass
from date_utils import DateObj


@dataclass
class Price:
    price: float
    currency_code: str


@dataclass
class Purchase:
    date: DateObj
    purchase_fmv: Price
    quantity: float
    ticker: str
