"""CLI entry point for the nz-companies-office tool."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from nz_companies_office.db.connection import close_driver
from nz_companies_office.graph.enrichment import compute_share_percentages
from nz_companies_office.graph.entity_resolution import entity_resolution
from nz_companies_office.graph.loader import load_database

DEFAULT_DATA_DIR = Path("data/raw/202606")


def load_db(*, skip_load: bool = False, root_dir: Path | None = None) -> None:
    """Drop and reload the full Neo4j graph."""
    load_database(skip_load=skip_load, root_dir=root_dir)
    close_driver()


def run_er() -> None:
    """Run the entity resolution pipeline."""
    entity_resolution()
    close_driver()


def run_enrich() -> None:
    """Run post-load enrichment (share percentages)."""
    compute_share_percentages()
    close_driver()


def _add_data_dir_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help=f"Path to CSV export directory (default: {DEFAULT_DATA_DIR})",
    )


def run() -> None:
    """Main CLI entry point."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(description="NZ Companies Office tools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser("fetch", help="Fetch company data from NZBN API and save to Neo4j")
    fetch_parser.add_argument("company_number", help="Companies Office company number")

    csv_fetch_parser = subparsers.add_parser("csv-fetch", help="Load a company from bulk CSV and save to Neo4j")
    csv_fetch_parser.add_argument("company_number", help="Companies Office company number")
    _add_data_dir_arg(csv_fetch_parser)

    load_db_parser = subparsers.add_parser("load-db", help="Drop and reload the full Neo4j graph")
    load_db_parser.add_argument("--skip-load", action="store_true", help="skip the CSV load step")
    load_db_parser.add_argument(
        "--root-dir",
        type=Path,
        default=None,
        help="Project root directory (default: auto-detected)",
    )

    subparsers.add_parser("er", help="Run entity resolution pipeline")
    subparsers.add_parser("enrich", help="Post-load enrichment (share percentages)")

    args = parser.parse_args()

    if args.command == "load-db":
        load_db(skip_load=args.skip_load, root_dir=args.root_dir)
    elif args.command == "er":
        run_er()
    elif args.command == "enrich":
        run_enrich()
