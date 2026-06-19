"""Client for querying the NZBN API for company information."""

from __future__ import annotations

import os
from datetime import date

import httpx

from nz_companies_office.models.company import Address
from nz_companies_office.models.company import AddressType
from nz_companies_office.models.company import Company
from nz_companies_office.models.company import CompanyStatus
from nz_companies_office.models.company import Director
from nz_companies_office.models.company import Shareholder


class NzbnClientError(Exception):
    """Raised when the NZBN API returns an error."""


class NzbnClient:
    """HTTP client for the NZBN public API.

    Fetches company details by NZBN or company number.

    Requires an API subscription key from https://portal.api.business.govt.nz.
    Pass via the constructor or set the NZBN_API_KEY environment variable.
    """

    BASE_URL = "https://api.business.govt.nz"

    def __init__(self, api_key: str | None = None, timeout: int = 30) -> None:
        """Initialize the client.

        Args:
            api_key: NZBN API subscription key. Falls back to NZBN_API_KEY env var.
            timeout: HTTP request timeout in seconds.
        """
        key = api_key or os.environ.get("NZBN_API_KEY")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if key:
            headers["Ocp-Apim-Subscription-Key"] = key
        self._client = httpx.Client(headers=headers, timeout=timeout)

    def get_company(self, company_number: str) -> Company:
        """Fetch company details by company number.

        Args:
            company_number: The NZ Companies Office company number.

        Returns:
            A Company model populated with API data.

        Raises:
            NzbnClientError: If the API returns an error.
        """
        url = f"{self.BASE_URL}/gateway/nzbn/rest/v1/nzbn/{company_number}"
        response = self._client.get(
            url,
            params={"entityIdType": "NZBN"},
        )
        if response.is_error:
            msg = f"NZBN API error: {response.status_code} {response.text}"
            raise NzbnClientError(msg)

        data = response.json()
        return self._parse_company(data)

    def _parse_company(self, data: dict) -> Company:
        """Parse raw API response into a Company model."""
        company_data = data.get("company", data)
        nzbn = company_data.get("nzbn", "")
        legal_name = company_data.get("legalName", "")
        status_raw = company_data.get("entityStatus", "")
        status = CompanyStatus.REGISTERED if status_raw == "Registered" else CompanyStatus.REMOVED
        entity_type = company_data.get("entityType", "")
        incorporation_raw = company_data.get("registrationDate", "")
        incorporation_date = date.fromisoformat(incorporation_raw) if incorporation_raw else None

        addresses = self._parse_addresses(company_data)
        directors = self._parse_directors(company_data)
        shareholders = self._parse_shareholders(company_data)

        return Company(
            company_number=company_number_from_nzbn(nzbn) or nzbn,
            name=legal_name,
            status=status,
            entity_type=entity_type,
            incorporation_date=incorporation_date,
            addresses=addresses,
            directors=directors,
            shareholders=shareholders,
            nzbn=nzbn,
        )

    def _parse_addresses(self, data: dict) -> list[Address]:
        """Extract addresses from API response data."""
        raw_addresses = data.get("addresses", [])
        return [
            Address(
                address_type=(
                    AddressType.REGISTERED_OFFICE if addr.get("type") == "registered" else AddressType.SERVICE
                ),
                street=addr.get("street", ""),
                suburb=addr.get("suburb"),
                city=addr.get("city"),
                postcode=addr.get("postcode"),
                country=addr.get("country", "New Zealand"),
            )
            for addr in raw_addresses
        ]

    def _parse_directors(self, data: dict) -> list[Director]:
        """Extract directors from API response data."""
        raw_directors = data.get("directors", [])
        return [
            Director(
                name=dr.get("fullName", ""),
                role=dr.get("role"),
                appointment_date=(date.fromisoformat(dr["appointmentDate"]) if dr.get("appointmentDate") else None),
            )
            for dr in raw_directors
        ]

    def _parse_shareholders(self, data: dict) -> list[Shareholder]:
        """Extract shareholders from API response data."""
        raw_shareholders = data.get("shareholdings", data.get("shareholders", []))
        return [
            Shareholder(
                name=sh.get("name", ""),
                share_count=int(sh.get("numberOfShares", sh.get("shareCount", 0))),
            )
            for sh in raw_shareholders
        ]


def company_number_from_nzbn(nzbn: str) -> str | None:  # noqa: ARG001
    """Extract the Companies Office number from an NZBN, if encoded."""
    return None
