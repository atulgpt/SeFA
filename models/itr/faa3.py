class FAA3:
    def __init__(self, org, purchase, purchase_price, peak_price, closing_price):
        self.org = org
        self.purchase = purchase
        self.purchase_price = purchase_price
        self.peak_price = peak_price
        self.closing_price = closing_price

    def __str__(self):
        return f"org = {self.org}, purchase = {self.purchase}, purchase_price = {self.purchase_price}, peak_price = {self.peak_price}, & closing_price = {self.closing_price}"
