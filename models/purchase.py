from date_utils import DateObj


class Price:
    def __init__(self, price: float, currency_code: str):
        self.price = price
        self.currency_code = currency_code

    def __str__(self):
        return f"price = {self.price} & currency_code = {self.currency_code}"


class Purchase:
    def __init__(
        self, date: DateObj, purchase_fmv: Price, quantity: float, ticker: str
    ):
        self.date = date
        self.purchase_fmv = purchase_fmv
        self.quantity = quantity
        self.ticker = ticker

    def __str__(self):
        return f"date = {self.date}, ticker = {self.ticker}, quantity = {self.quantity} & purchase_fmv = {self.purchase_fmv}"
