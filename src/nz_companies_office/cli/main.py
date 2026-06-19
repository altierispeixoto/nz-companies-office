"""CLI entry point for the nz-companies-office tool."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from nz_companies_office.clients.nzbn import NzbnClient
from nz_companies_office.clients.nzbn import NzbnClientError
from nz_companies_office.db.connection import close_driver
from nz_companies_office.db.connection import get_driver
from nz_companies_office.db.repository import save_company
from nz_companies_office.loaders.csv_loader import CsvCompanyLoader

DEFAULT_DATA_DIR = Path("data/raw/202606")


def fetch(company_number: str) -> None:
    """Fetch company data from NZBN API and persist to Neo4j."""
    client = NzbnClient()
    try:
        company = client.get_company(company_number)
    except NzbnClientError as exc:
        print(f"Error fetching company {company_number}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    driver = get_driver()
    try:
        save_company(driver, company)
    finally:
        close_driver()

    print(f"Saved {company.name} ({company.company_number}) to Neo4j")
    print(f"  Directors: {len(company.directors)}")
    print(f"  Shareholders: {len(company.shareholders)}")
    print(f"  Addresses: {len(company.addresses)}")


def csv_fetch(company_number: str, data_dir: Path) -> None:
    """Load a company from bulk CSV and save to Neo4j."""
    loader = CsvCompanyLoader(data_dir)
    company = loader.get_company(company_number)
    if company is None:
        print(f"Company {company_number} not found in CSV data", file=sys.stderr)
        raise SystemExit(1)

    driver = get_driver()
    try:
        save_company(driver, company)
    finally:
        close_driver()

    print(f"Saved {company.name} ({company.company_number}) to Neo4j")
    print(f"  Directors: {len(company.directors)}")
    print(f"  Shareholders: {len(company.shareholders)}")
    print(f"  Addresses: {len(company.addresses)}")


def _add_data_dir_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help=f"Path to CSV export directory (default: {DEFAULT_DATA_DIR})",
    )


def run() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="NZ Companies Office tools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser("fetch", help="Fetch company data from NZBN API and save to Neo4j")
    fetch_parser.add_argument("company_number", help="Companies Office company number")

    csv_fetch_parser = subparsers.add_parser("csv-fetch", help="Load a company from bulk CSV and save to Neo4j")
    csv_fetch_parser.add_argument("company_number", help="Companies Office company number")
    _add_data_dir_arg(csv_fetch_parser)

    args = parser.parse_args()

    if args.command == "fetch":
        fetch(args.company_number)
    elif args.command == "csv-fetch":
        csv_fetch(args.company_number, args.data_dir)
