"""Tests for CsvCompanyLoader."""

from __future__ import annotations

import csv
from datetime import date
from typing import TYPE_CHECKING

import pytest

from nz_companies_office.loaders.csv_loader import CsvCompanyLoader
from nz_companies_office.models.company import AddressType
from nz_companies_office.models.company import CompanyStatus

if TYPE_CHECKING:
    from pathlib import Path


def _write_csv(path: Path, filename: str, rows: list[list[str]]) -> Path:
    """Write a minimal CSV to *path/filename* and return the full path."""
    filepath = path / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with filepath.open("w", newline="") as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(row)
    return filepath


_CORE_HEADER = [
    "NZBN",
    "COMPANY_IDENTIFIER",
    "ENTITY_NAME",
    "REGISTRATION_DATE",
    "REMOVAL_DATE",
    "ENTITY_TYPE",
    "ENTITY_STATUS",
]

_DIRECTOR_HEADER = [
    "NZBN",
    "ENTITY_NAME",
    "START_DATE",
    "FIRST_NAME",
    "MIDDLE_NAMES",
    "LAST_NAME",
    "ASIC_DIR_YN",
    "ACN",
    "ASIC_COMPANY_NAME",
]

_SHAREHOLDER_HEADER = [
    "NZBN",
    "ENTITY_NAME",
    "SH_NAME",
    "SH_TYPE",
    "START_DATE",
    "SH_STATUS",
    "PARCEL_IDENTIFIER",
    "ASSIGNMENT_IDENTIFIER",
    "NUMBER_OF_SHARES",
    "SH_EXTENSIVE_SHAREHOLDING_YN",
    "SH_ADDRESS_PAF_ID",
    "SH_ADDRESS_CARE_OF",
    "SH_ADDRESS_1",
    "SH_ADDRESS_2",
    "SH_ADDRESS_3",
    "SH_ADDRESS_4",
    "SH_ADDRESS_POSTCODE",
    "SH_ADDRESS_COUNTRY",
]

_REG_OFFICE_HEADER = [
    "NZBN",
    "ENTITY_NAME",
    "START_DATE",
    "REGISTERED_OFFICE_ADDRESS_PAF_ID",
    "REGISTERED_OFFICE_ADDRESS_CARE_OF",
    "REGISTERED_OFFICE_ADDRESS_1",
    "REGISTERED_OFFICE_ADDRESS_2",
    "REGISTERED_OFFICE_ADDRESS_3",
    "REGISTERED_OFFICE_ADDRESS_4",
    "REGISTERED_OFFICE_ADDRESS_POSTCODE",
    "REGISTERED_OFFICE_ADDRESS_COUNTRY",
]

_ADDR_SERVICE_HEADER = [
    "NZBN",
    "ENTITY_NAME",
    "START_DATE",
    "ADDRESS_FOR_SERVICE_PAF_ID",
    "ADDRESS_FOR_SERVICE_CARE_OF",
    "ADDRESS_FOR_SERVICE_1",
    "ADDRESS_FOR_SERVICE_2",
    "ADDRESS_FOR_SERVICE_3",
    "ADDRESS_FOR_SERVICE_4",
    "ADDRESS_FOR_SERVICE_POSTCODE",
    "ADDRESS_FOR_SERVICE_COUNTRY",
]


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create a temporary CSV data directory with a small set of test rows."""
    _write_csv(
        tmp_path,
        "companies_core_data.csv",
        [
            _CORE_HEADER,
            ["9429031075473", "3405451", "PARROT ANALYTICS LIMITED", "01/06/2011", "", "LTD", "Registered"],
            ["9429031193450", "3301188", "PEAZY LIMITED", "09/03/2011", "20/11/2012", "LTD", "Removed"],
        ],
    )
    _write_csv(
        tmp_path,
        "companies_director.csv",
        [
            _DIRECTOR_HEADER,
            ["9429031075473", "PARROT ANALYTICS LIMITED", "01/06/2011", "Wared", "", "SEGER", "", "", ""],
            ["9429031075473", "PARROT ANALYTICS LIMITED", "12/11/2024", "Robert", "Joel", "PAUL", "", "", ""],
        ],
    )
    _write_csv(
        tmp_path,
        "companies_shareholder.csv",
        [
            _SHAREHOLDER_HEADER,
            [
                "9429031075473",
                "PARROT ANALYTICS LIMITED",
                "ICEHOUSE VENTURES NOMINEES LIMITED",
                "Shareholder Company",
                "04/06/2022",
                "active",
                "3970478",
                "4155569",
                "2407427",
                "Y",
                "",
                "",
                "The Textile Centre",
                "Level 4, 117-125 St Georges Bay Road",
                "Parnell, Auckland",
                "",
                "1052",
                "NEW ZEALAND",
            ],
            [
                "9429031075473",
                "PARROT ANALYTICS LIMITED",
                "Wared  SEGER",
                "Shareholder Individual",
                "16/11/2020",
                "active",
                "4419770",
                "4574011",
                "882820",
                "Y",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
            ],
        ],
    )
    _write_csv(
        tmp_path,
        "companies_registered_office_address.csv",
        [
            _REG_OFFICE_HEADER,
            [
                "9429031075473",
                "PARROT ANALYTICS LIMITED",
                "13/11/2023",
                "",
                "Directors of Parrot Analytics Limited",
                "Suite 1",
                "20 Augustus Terrace",
                "Auckland",
                "",
                "1052",
                "NEW ZEALAND",
            ],
        ],
    )
    _write_csv(
        tmp_path,
        "companies_address_for_service.csv",
        [
            _ADDR_SERVICE_HEADER,
            [
                "9429031075473",
                "PARROT ANALYTICS LIMITED",
                "20/11/2023",
                "",
                "Directors of Parrot Analytics Limited",
                "Suite 1",
                "20 Augustus Terrace",
                "Auckland",
                "",
                "1052",
                "NEW ZEALAND",
            ],
        ],
    )
    return tmp_path


_KNOWN_NUMBER = "3405451"
_KNOWN_NZBN = "9429031075473"
_REMOVED_NUMBER = "3301188"
_INCORP_DATE = date(2011, 6, 1)
_WARED_SEGER_SHARES = 882820


class TestCsvCompanyLoader:
    """Tests for CsvCompanyLoader using temporary CSV files."""

    def test_get_company_found(self, data_dir: Path) -> None:
        """get_company returns a Company for a known company number."""
        loader = CsvCompanyLoader(data_dir)
        company = loader.get_company(_KNOWN_NUMBER)
        assert company is not None
        assert company.company_number == _KNOWN_NUMBER
        assert company.nzbn == _KNOWN_NZBN
        assert company.name == "PARROT ANALYTICS LIMITED"
        assert company.status == CompanyStatus.REGISTERED
        assert company.entity_type == "LTD"

    def test_get_company_incorporation_date(self, data_dir: Path) -> None:
        """incorporation_date is parsed correctly from DD/MM/YYYY."""
        loader = CsvCompanyLoader(data_dir)
        company = loader.get_company(_KNOWN_NUMBER)
        assert company is not None
        assert company.incorporation_date == _INCORP_DATE

    def test_get_company_removed_status(self, data_dir: Path) -> None:
        """Removed companies have REMOVED status."""
        loader = CsvCompanyLoader(data_dir)
        company = loader.get_company(_REMOVED_NUMBER)
        assert company is not None
        assert company.status == CompanyStatus.REMOVED

    def test_get_company_missing(self, data_dir: Path) -> None:
        """get_company returns None for an unknown company number."""
        loader = CsvCompanyLoader(data_dir)
        company = loader.get_company("9999999")
        assert company is None

    def test_directors(self, data_dir: Path) -> None:
        """Directors are parsed from the director CSV."""
        loader = CsvCompanyLoader(data_dir)
        company = loader.get_company(_KNOWN_NUMBER)
        assert company is not None
        director_count = 2
        assert len(company.directors) == director_count
        assert company.directors[0].name == "Wared SEGER"
        assert company.directors[0].appointment_date is not None
        assert company.directors[1].name == "Robert Joel PAUL"

    def test_shareholders(self, data_dir: Path) -> None:
        """Shareholders are parsed from the shareholder CSV."""
        loader = CsvCompanyLoader(data_dir)
        company = loader.get_company(_KNOWN_NUMBER)
        assert company is not None
        shareholder_count = 2
        icehouse_shares = 2407427
        assert len(company.shareholders) == shareholder_count
        assert company.shareholders[0].name == "ICEHOUSE VENTURES NOMINEES LIMITED"
        assert company.shareholders[0].share_count == icehouse_shares
        assert company.shareholders[1].share_count == _WARED_SEGER_SHARES

    def test_addresses(self, data_dir: Path) -> None:
        """Registered office and service addresses are parsed."""
        loader = CsvCompanyLoader(data_dir)
        company = loader.get_company(_KNOWN_NUMBER)
        assert company is not None
        address_count = 2
        assert len(company.addresses) == address_count
        reg = next(a for a in company.addresses if a.address_type == AddressType.REGISTERED_OFFICE)
        svc = next(a for a in company.addresses if a.address_type == AddressType.SERVICE)
        assert reg.street == "Suite 1"
        assert reg.suburb == "20 Augustus Terrace"
        assert reg.city == "Auckland"
        assert reg.postcode == "1052"
        assert reg.country == "NEW ZEALAND"
        assert svc.city == "Auckland"

    def test_iter_all(self, data_dir: Path) -> None:
        """iter_all yields all companies from the core data."""
        loader = CsvCompanyLoader(data_dir)
        companies = list(loader.iter_all())
        company_count = 2
        assert len(companies) == company_count
        numbers = {c.company_number for c in companies}
        assert numbers == {_KNOWN_NUMBER, _REMOVED_NUMBER}
