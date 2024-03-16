import sys, os
from types import MappingProxyType

script_path = os.path.realpath(__file__)
script_folder = os.path.dirname(script_path)
top_folder = os.path.dirname(script_folder)
sys.path.insert(1, os.path.join(top_folder, "models"))
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
