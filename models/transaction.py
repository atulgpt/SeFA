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

    def total_value(self) -> float:
        """
        Value of the whole leg in the currency it was traded in
        """
        return round(self.fmv.price * self.quantity, 2)


@dataclass
class TransactionWithTicker:
    purchase: Transaction
    ticker: str
