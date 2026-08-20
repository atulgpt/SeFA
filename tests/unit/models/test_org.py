import pytest

from sefa.models.org import Organization

VALID_ORGANIZATION_FIELDS = {
    "country_name": "United States Of America",
    "country_code": "2",
    "name": "Adobe Incorporation",
    "address": "345 Park Avenue San Jose CA",
    "nature": "Listed",
    "zip_code": "95110",
}


def test_organization_without_comma_is_built():
    org = Organization(**VALID_ORGANIZATION_FIELDS)
    assert org.name == "Adobe Incorporation"
    assert org.address == "345 Park Avenue San Jose CA"


def test_organization_name_with_comma_raises():
    with pytest.raises(AssertionError) as error:
        Organization(**{**VALID_ORGANIZATION_FIELDS, "name": "Adobe, Incorporation"})
    assert (
        "Organization name must not contain a ','."
        + " Found name = Adobe, Incorporation"
        in str(error.value)
    )


def test_organization_address_with_comma_raises():
    with pytest.raises(AssertionError) as error:
        Organization(
            **{**VALID_ORGANIZATION_FIELDS, "address": "345 Park Avenue, San Jose, CA"}
        )
    assert (
        "Organization address must not contain a ','."
        + " Found address = 345 Park Avenue, San Jose, CA"
        in str(error.value)
    )
