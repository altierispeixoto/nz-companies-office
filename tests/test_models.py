"""Tests for the company data models."""

from __future__ import annotations

from datetime import date

from nz_companies_office.domain.models import Address
from nz_companies_office.domain.models import AddressType
from nz_companies_office.domain.models import Company
from nz_companies_office.domain.models import CompanyStatus
from nz_companies_office.domain.models import Director
from nz_companies_office.domain.models import Shareholder


def test_company_defaults() -> None:
    """Company created with only required fields uses sensible defaults."""
    company = Company(company_number="12345", name="Test Ltd")
    assert company.company_number == "12345"
    assert company.name == "Test Ltd"
    assert company.status == CompanyStatus.REGISTERED
    assert company.entity_type is None
    assert company.incorporation_date is None
    assert company.addresses == []
    assert company.directors == []
    assert company.shareholders == []
    assert company.nzbn is None


def test_company_full() -> None:
    """Company with all fields populated stores values correctly."""
    company = Company(
        company_number="3405451",
        name="Parrot Analytics Limited",
        status=CompanyStatus.REGISTERED,
        entity_type="LTD",
        incorporation_date=date(2011, 5, 30),
        addresses=[
            Address(
                address_type=AddressType.REGISTERED_OFFICE,
                street="1 Queen Street",
                city="Auckland",
            ),
        ],
        directors=[Director(name="John Doe", role="Director", appointment_date=date(2020, 1, 1))],
        shareholders=[Shareholder(name="John Doe", share_count=1000)],
        nzbn="9429031193450",
    )
    assert company.company_number == "3405451"
    assert company.incorporation_date == date(2011, 5, 30)
    assert len(company.addresses) == 1
    assert len(company.directors) == 1
    assert len(company.shareholders) == 1
    assert company.nzbn == "9429031193450"


def test_address_default_country() -> None:
    """Address defaults to New Zealand when country is not specified."""
    addr = Address(address_type=AddressType.REGISTERED_OFFICE, street="1 Queen St", city="Auckland")
    assert addr.country == "New Zealand"


def test_director_minimal() -> None:
    """Director created with only name has None for optional fields."""
    director = Director(name="Jane Smith")
    assert director.name == "Jane Smith"
    assert director.role is None
    assert director.appointment_date is None


def test_shareholder() -> None:
    """Shareholder stores share count correctly."""
    expected_count = 2407427
    shareholder = Shareholder(name="Icehouse Ventures Nominees Limited", share_count=expected_count)
    assert shareholder.share_count == expected_count
    assert shareholder.share_type is None
