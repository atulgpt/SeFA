from dataclasses import dataclass


@dataclass
class Organization:
    country_name: str
    country_code: str
    name: str
    address: str
    nature: str
    zip_code: str

    def __post_init__(self):
        assert "," not in self.name, (
            "Organization name must not contain a ','."
            + f" Found name = {self.name}"
        )
        assert "," not in self.address, (
            "Organization address must not contain a ','."
            + f" Found address = {self.address}"
        )
