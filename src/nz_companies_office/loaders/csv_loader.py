"""Load company data from bulk Companies Office CSV exports."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING
from typing import ClassVar

import pandas as pd

from nz_companies_office.models.company import Address
from nz_companies_office.models.company import AddressType
from nz_companies_office.models.company import Company
from nz_companies_office.models.company import CompanyStatus
from nz_companies_office.models.company import Director
from nz_companies_office.models.company import Shareholder

if TYPE_CHECKING:
    from collections.abc import Iterator

_DDMMYYYY = r"(\d{2})/(\d{2})/(\d{4})"


def _parse_date(val: object) -> date | None:
    """Parse a DD/MM/YYYY string into a date, or None."""
    if not isinstance(val, str) or not val.strip():
        return None
    return date(
        int(val[6:10]),
        int(val[3:5]),
        int(val[0:2]),
    )


def _build_director_name(row: dict) -> str:
    """Build a full name from FIRST_NAME, MIDDLE_NAMES, LAST_NAME."""
    parts = [row.get("FIRST_NAME", ""), row.get("MIDDLE_NAMES", ""), row.get("LAST_NAME", "")]
    return " ".join(p for p in parts if p).strip() or row.get("ENTITY_NAME", "")


def _build_address_components(
    row: dict,
    prefix: str,
) -> tuple[str, str | None, str | None, str | None, str | None]:
    """Extract (street, suburb, city, postcode, country) from address columns."""
    city_3 = (row.get(f"{prefix}_3") or "").strip()
    city_4 = (row.get(f"{prefix}_4") or "").strip()
    city = (city_3 or None) or (city_4 or None)
    return (
        row.get(f"{prefix}_1", ""),
        row.get(f"{prefix}_2") or None,
        city,
        row.get(f"{prefix}_POSTCODE") or None,
        row.get(f"{prefix}_COUNTRY") or None,
    )


def _address_from_components(
    street: str,
    suburb: str | None,
    city: str | None,
    postcode: str | None,
    country: str | None,
    address_type: AddressType,
) -> Address:
    return Address(
        address_type=address_type,
        street=street,
        suburb=suburb,
        city=city,
        postcode=postcode,
        country=country or "",
    )


class CsvCompanyLoader:
    """Loads company data from a bulk CSV export directory.

    Accepts a path like ``data/raw/202606/`` containing the standard
    Companies Office CSV files.  Loads DataFrames lazily on first access.
    """

    _FILENAMES: ClassVar[dict[str, str]] = {
        "core": "companies_core_data.csv",
        "director": "companies_director.csv",
        "shareholder": "companies_shareholder.csv",
        "registered_office": "companies_registered_office_address.csv",
        "address_for_service": "companies_address_for_service.csv",
        "public_address": "companies_public_address.csv",
    }

    def __init__(self, data_dir: str | Path) -> None:
        """Initialise with the directory containing the CSV export files."""
        self._data_dir = Path(data_dir)
        self._dfs: dict[str, pd.DataFrame | None] = dict.fromkeys(self._FILENAMES)

    # ------------------------------------------------------------------
    # Lazy-loaded DataFrames
    # ------------------------------------------------------------------

    def _load(self, key: str) -> pd.DataFrame:
        if self._dfs.get(key) is None:
            path = self._data_dir / self._FILENAMES[key]
            self._dfs[key] = pd.read_csv(path, dtype=str, keep_default_na=False)
        return self._dfs[key]

    @property
    def _core(self) -> pd.DataFrame:
        return self._load("core")

    @property
    def _director(self) -> pd.DataFrame:
        return self._load("director")

    @property
    def _shareholder(self) -> pd.DataFrame:
        return self._load("shareholder")

    @property
    def _reg_office(self) -> pd.DataFrame:
        return self._load("registered_office")

    @property
    def _addr_service(self) -> pd.DataFrame:
        return self._load("address_for_service")

    @property
    def _public_addr(self) -> pd.DataFrame:
        return self._load("public_address")

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------

    def _nzbn_for_number(self, company_number: str) -> str | None:
        """Resolve company number → NZBN."""
        mask = self._core["COMPANY_IDENTIFIER"] == company_number
        matches = self._core.loc[mask, "NZBN"]
        return matches.iloc[0] if not matches.empty else None

    # ------------------------------------------------------------------
    # Single-company builders
    # ------------------------------------------------------------------

    def _build_company(self, core_row: dict) -> Company:
        nzbn = core_row.get("NZBN", "")
        company_number = core_row.get("COMPANY_IDENTIFIER", "")
        status_str = core_row.get("ENTITY_STATUS", "")
        status = CompanyStatus.REGISTERED if status_str.strip().lower() == "registered" else CompanyStatus.REMOVED

        return Company(
            company_number=company_number,
            nzbn=nzbn,
            name=core_row.get("ENTITY_NAME", ""),
            status=status,
            entity_type=core_row.get("ENTITY_TYPE", ""),
            incorporation_date=_parse_date(core_row.get("REGISTRATION_DATE")),
            addresses=self._build_addresses(nzbn),
            directors=self._build_directors(nzbn),
            shareholders=self._build_shareholders(nzbn),
        )

    def _build_directors(self, nzbn: str) -> list[Director]:
        mask = self._director["NZBN"] == nzbn
        subset = self._director.loc[mask]
        directors: list[Director] = []
        for _, row in subset.iterrows():
            directors.append(
                Director(
                    name=_build_director_name(row.to_dict()),
                    role=None,
                    appointment_date=_parse_date(row.get("START_DATE")),
                ),
            )
        return directors

    def _build_shareholders(self, nzbn: str) -> list[Shareholder]:
        mask = self._shareholder["NZBN"] == nzbn
        subset = self._shareholder.loc[mask]
        shareholders: list[Shareholder] = []
        for _, row in subset.iterrows():
            try:
                share_count = int(row.get("NUMBER_OF_SHARES", "0"))
            except (ValueError, TypeError):
                share_count = 0
            shareholders.append(
                Shareholder(
                    name=row.get("SH_NAME", ""),
                    share_count=share_count,
                ),
            )
        return shareholders

    def _build_addresses(self, nzbn: str) -> list[Address]:
        addresses: list[Address] = []

        # Registered office
        mask = self._reg_office["NZBN"] == nzbn
        if mask.any():
            row = self._reg_office.loc[mask].iloc[0].to_dict()
            street, suburb, city, postcode, country = _build_address_components(
                row,
                "REGISTERED_OFFICE_ADDRESS",
            )
            addresses.append(
                _address_from_components(
                    street,
                    suburb,
                    city,
                    postcode,
                    country,
                    AddressType.REGISTERED_OFFICE,
                ),
            )

        # Address for service
        mask = self._addr_service["NZBN"] == nzbn
        if mask.any():
            row = self._addr_service.loc[mask].iloc[0].to_dict()
            street, suburb, city, postcode, country = _build_address_components(
                row,
                "ADDRESS_FOR_SERVICE",
            )
            addresses.append(
                _address_from_components(
                    street,
                    suburb,
                    city,
                    postcode,
                    country,
                    AddressType.SERVICE,
                ),
            )

        return addresses

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_company(self, company_number: str) -> Company | None:
        """Fetch a single company by its Companies Office number.

        Args:
            company_number: e.g. ``"3405451"``

        Returns:
            A Company model, or None if not found.
        """
        nzbn = self._nzbn_for_number(company_number)
        if nzbn is None:
            return None
        mask = self._core["NZBN"] == nzbn
        row = self._core.loc[mask].iloc[0].to_dict()
        return self._build_company(row)

    def iter_all(self) -> Iterator[Company]:
        """Yield every company from the core data CSV."""
        for _, row in self._core.iterrows():
            yield self._build_company(row.to_dict())
