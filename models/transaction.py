from dataclasses import dataclass
from utils.date_utils import DateObj


@dataclass
class Price:
    price: float
    currency_code: str


@dataclass
class Transaction:
    date: DateObj
    fmv: Price
    quantity: float


@dataclass
class TransactionWithTicker:
    purchase: Transaction
    ticker: str
