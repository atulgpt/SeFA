class Organization:
    def __init__(self, country_name, name, address, nature, zip_code=999999):
        self.country_name = country_name
        self.name = name
        self.address = address
        self.nature = nature
        self.zip_code = zip_code

    def __str__(self):
        return f"name = {self.name}, address = {self.address}, country = {self.country_name}, zip = ${self.zip_code} & nature = {self.nature}"
