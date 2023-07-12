class Purchase:
    def __init__(self, date, purchase_fmv, quantity, ticker):
        self.date = date
        self.purchase_fmv = purchase_fmv
        self.quantity = quantity
        self.ticker = ticker

    def __str__(self):
        return f"date = {self.date}, ticker = {self.ticker}, quantity = {self.quantity} & purchase_fmv = {self.purchase_fmv}"


class Price:
    def __init__(self, price, currency_code):
        self.price = price
        self.currency_code = currency_code

    def __str__(self):
        return f"price = {self.price} & currency_code = {self.currency_code}"
