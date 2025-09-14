from dataclasses import dataclass


@dataclass
class Organization:
    country_name: str
    country_code: str
    name: str
    address: str
    nature: str
    zip_code: str
