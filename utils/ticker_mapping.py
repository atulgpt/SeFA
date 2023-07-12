import sys
from types import MappingProxyType

sys.path.insert(1, "../models")
from org import Organization

ticker_org_info = MappingProxyType(
    {
        "adbe": Organization(
            name="Adobe Incorporation",
            address="345 Park Avenue San Jose, CA",
            country_name="2 - United States",
            zip_code="95110",
            nature="Listed",
        ),
    }
)

ticker_currency_info = MappingProxyType(
    {
        "adbe": "usd",
    }
)
