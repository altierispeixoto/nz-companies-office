"""Tests for the CLI runner."""

from __future__ import annotations

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from nz_companies_office.cli.main import fetch
from nz_companies_office.clients.nzbn import NzbnClientError
from nz_companies_office.models.company import Company
from nz_companies_office.models.company import CompanyStatus


class TestFetch:
    """Tests for the fetch CLI command."""

    def test_fetch_calls_save_company(self) -> None:
        """Fetch retrieves a company and persists it."""
        expected_company = Company(
            company_number="12345",
            name="Test Ltd",
            status=CompanyStatus.REGISTERED,
        )

        with (
            patch("nz_companies_office.cli.main.NzbnClient") as mock_client_cls,
            patch("nz_companies_office.cli.main.get_driver") as mock_get_driver,
            patch("nz_companies_office.cli.main.save_company") as mock_save,
            patch("nz_companies_office.cli.main.close_driver") as mock_close,
        ):
            mock_client_cls.return_value.get_company.return_value = expected_company
            mock_get_driver.return_value = MagicMock()

            fetch("12345")

            mock_client_cls.return_value.get_company.assert_called_once_with("12345")
            mock_save.assert_called_once_with(mock_get_driver.return_value, expected_company)
            mock_close.assert_called_once()

    def test_fetch_exits_on_api_error(self) -> None:
        """Fetch exits with error when NZBN API returns an error."""
        with (
            patch("nz_companies_office.cli.main.NzbnClient") as mock_client_cls,
        ):
            mock_client_cls.return_value.get_company.side_effect = NzbnClientError("API error")

            with pytest.raises(SystemExit, match="1"):
                fetch("bad-number")
