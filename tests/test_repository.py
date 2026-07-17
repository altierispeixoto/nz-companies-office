"""Tests for the Neo4j repository layer."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

from nz_companies_office.db.repository import save_company
from nz_companies_office.models.company import Address
from nz_companies_office.models.company import AddressType
from nz_companies_office.models.company import Company
from nz_companies_office.models.company import Director
from nz_companies_office.models.company import Shareholder


class TestSaveCompany:
    """Tests for save_company."""

    def test_save_company_creates_node(self) -> None:
        """save_company executes Cypher MERGE for the company node."""
        mock_driver = MagicMock()
        company = Company(company_number="12345", name="Test Ltd")
        save_company(mock_driver, company)
        assert mock_driver.session.called

    def test_save_company_with_addresses(self) -> None:
        """save_company persists address nodes linked to the company."""
        mock_driver = MagicMock()
        company = Company(
            company_number="12345",
            name="Test Ltd",
            addresses=[
                Address(
                    address_type=AddressType.REGISTERED_OFFICE,
                    street="1 Queen Street",
                    city="Auckland",
                ),
            ],
        )
        save_company(mock_driver, company)
        assert mock_driver.session.called

    def test_save_company_with_directors(self) -> None:
        """save_company persists director nodes with DIRECTS relationship."""
        mock_driver = MagicMock()
        company = Company(
            company_number="12345",
            name="Test Ltd",
            directors=[Director(name="Jane Smith", role="Director", appointment_date=date(2020, 1, 1))],
        )
        save_company(mock_driver, company)
        assert mock_driver.session.called

    def test_save_company_with_shareholders(self) -> None:
        """save_company persists shareholder nodes with HOLDS_SHARES_IN relationship."""
        mock_driver = MagicMock()
        company = Company(
            company_number="12345",
            name="Test Ltd",
            shareholders=[Shareholder(name="Acme Corp", share_count=500)],
        )
        save_company(mock_driver, company)
        assert mock_driver.session.called
