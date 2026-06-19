"""Tests for the NZBN API client."""

from __future__ import annotations

from datetime import date

import httpx
import pytest

from nz_companies_office.clients.nzbn import NzbnClient
from nz_companies_office.clients.nzbn import NzbnClientError
from nz_companies_office.models.company import CompanyStatus


def _mock_transport(responses: list[httpx.Response]) -> httpx.MockTransport:
    """Create a MockTransport that returns the given responses in sequence."""
    iterator = iter(responses)

    def handler(request: httpx.Request) -> httpx.Response:  # noqa: ARG001
        return next(iterator)

    return httpx.MockTransport(handler)


class TestNzbnClient:
    """Tests for NzbnClient using httpx mock transport."""

    def _client_with_mock(self, response: httpx.Response) -> NzbnClient:
        """Create an NzbnClient wired to a mock transport returning the given response."""
        transport = _mock_transport([response])
        client = NzbnClient()
        client._client = httpx.Client(transport=transport)  # noqa: SLF001
        return client

    def test_get_company_parses_core_fields(self) -> None:
        """get_company returns a Company with parsed top-level fields."""
        api_data = {
            "company": {
                "nzbn": "9429031193450",
                "legalName": "Parrot Analytics Limited",
                "entityStatus": "Registered",
                "entityType": "LTD",
                "registrationDate": "2011-05-30",
            },
        }
        client = self._client_with_mock(httpx.Response(200, json=api_data))

        company = client.get_company("3405451")
        assert company.name == "Parrot Analytics Limited"
        assert company.nzbn == "9429031193450"
        assert company.status == CompanyStatus.REGISTERED
        assert company.entity_type == "LTD"
        assert company.incorporation_date == date(2011, 5, 30)
        assert company.addresses == []
        assert company.directors == []
        assert company.shareholders == []

    def test_get_company_api_error(self) -> None:
        """get_company raises NzbnClientError on non-2xx response."""
        client = self._client_with_mock(httpx.Response(404, text="Not found"))

        with pytest.raises(NzbnClientError, match="NZBN API error: 404"):
            client.get_company("bad-number")

    def test_get_company_with_addresses(self) -> None:
        """get_company parses address data from the API response."""
        api_data = {
            "company": {
                "nzbn": "9429031193450",
                "legalName": "Test Ltd",
                "entityStatus": "Registered",
                "addresses": [
                    {
                        "type": "registered",
                        "street": "1 Queen Street",
                        "city": "Auckland",
                        "country": "New Zealand",
                    },
                ],
            },
        }
        client = self._client_with_mock(httpx.Response(200, json=api_data))

        company = client.get_company("12345")
        assert len(company.addresses) == 1
        assert company.addresses[0].street == "1 Queen Street"
        assert company.addresses[0].city == "Auckland"

    def test_get_company_with_directors(self) -> None:
        """get_company parses director data from the API response."""
        api_data = {
            "company": {
                "nzbn": "9429031193450",
                "legalName": "Test Ltd",
                "entityStatus": "Registered",
                "directors": [
                    {"fullName": "John Doe", "role": "Director", "appointmentDate": "2020-01-01"},
                ],
            },
        }
        client = self._client_with_mock(httpx.Response(200, json=api_data))

        company = client.get_company("12345")
        assert len(company.directors) == 1
        assert company.directors[0].name == "John Doe"
        assert company.directors[0].appointment_date == date(2020, 1, 1)

    def test_get_company_with_shareholders(self) -> None:
        """get_company parses shareholder data from the API response."""
        expected_count = 2407427
        api_data = {
            "company": {
                "nzbn": "9429031193450",
                "legalName": "Test Ltd",
                "entityStatus": "Registered",
                "shareholders": [
                    {"name": "Icehouse Ventures Nominees Limited", "numberOfShares": expected_count},
                ],
            },
        }
        client = self._client_with_mock(httpx.Response(200, json=api_data))

        company = client.get_company("12345")
        assert len(company.shareholders) == 1
        assert company.shareholders[0].name == "Icehouse Ventures Nominees Limited"
        assert company.shareholders[0].share_count == expected_count
