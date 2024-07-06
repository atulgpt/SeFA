from dataclasses import dataclass


@dataclass
class Organization:
    country_name: str
    name: str
    address: str
    nature: str
    zip_code: str
