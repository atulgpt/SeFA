import typing as t

from models.org import Organization

ticker_org_info: t.Dict[str, Organization] = {
    "adbe": Organization(
        name="Adobe Incorporation",
        address="345 Park Avenue San Jose CA",
        country_name="United States Of America",
        country_code="2",
        zip_code="95110",
        nature="Listed",
    ),
}

ticker_currency_info: t.Dict[str, str] = {
    "adbe": "USD",
    "msft": "USD",
    "crm": "USD",
}
