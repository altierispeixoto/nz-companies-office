"""CLI entry point for the nz-companies-office tool."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import colorlog

from nz_companies_office.config import SETTINGS
from nz_companies_office.db.connection import close_driver
from nz_companies_office.graph.enrichment import compute_share_percentages
from nz_companies_office.graph.entity_resolution import entity_resolution
from nz_companies_office.graph.geocode import geocode as run_geocode_pipeline
from nz_companies_office.graph.geocode import prepare_linz_cache
from nz_companies_office.graph.loader import load_database


def load_db(*, skip_load: bool = False, root_dir: Path | None = None) -> None:
    """Drop and reload the full Neo4j graph."""
    load_database(skip_load=skip_load, root_dir=root_dir)
    close_driver()


def run_er() -> None:
    """Run the entity resolution pipeline."""
    entity_resolution()
    close_driver()


def run_geocode(
    *,
    export_path: Path | None = None,
    result_path: Path | None = None,
    shp_path: Path | None = None,
    cache_path: Path | None = None,
    data_dir: Path | None = None,
    sample: int | None = None,
) -> None:
    """Run the reverse geocoding pipeline."""
    run_geocode_pipeline(
        export_path=export_path,
        result_path=result_path,
        shp_path=shp_path,
        cache_path=cache_path,
        data_dir=data_dir,
        sample=sample,
    )


def run_enrich() -> None:
    """Run post-load enrichment (share percentages)."""
    compute_share_percentages()
    close_driver()


def _add_data_dir_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help=f"Path to CSV export directory (default: {SETTINGS.raw_data_dir})",
    )


def run() -> None:
    """Main CLI entry point."""
    handler = colorlog.StreamHandler(stream=sys.stdout)
    handler.setFormatter(
        colorlog.ColoredFormatter(
            fmt="%(log_color)s%(message)s%(reset)s",
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red,bg_white",
            },
        ),
    )
    logging.basicConfig(level=logging.INFO, handlers=[handler])

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

    prepare_linz_parser = subparsers.add_parser("prepare-linz", help="Transform LINZ shapefile into a cached CSV")
    prepare_linz_parser.add_argument("--shp-path", type=Path, default=None, help="Path to LINZ shapefile (.shp)")
    prepare_linz_parser.add_argument("--cache-path", type=Path, default=None, help="Output path for cached CSV")

    geocode_parser = subparsers.add_parser("geocode", help="Reverse geocode Address nodes using LINZ NZ Addresses")
    geocode_parser.add_argument("--export-path", type=Path, default=None, help="Path to write extracted addresses CSV")
    geocode_parser.add_argument("--result-path", type=Path, default=None, help="Path to write geocoded results CSV")
    geocode_parser.add_argument("--shp-path", type=Path, default=None, help="Path to LINZ shapefile (.shp)")
    geocode_parser.add_argument("--cache-path", type=Path, default=None, help="Path to LINZ cache")
    geocode_parser.add_argument("--data-dir", type=Path, default=None, help="Path to raw CSV data directory")
    geocode_parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Run on a random sample of N addresses (test mode)",
    )

    args = parser.parse_args()

    if args.command == "load-db":
        load_db(skip_load=args.skip_load, root_dir=args.root_dir)
    elif args.command == "er":
        run_er()
    elif args.command == "enrich":
        run_enrich()
    elif args.command == "prepare-linz":
        prepare_linz_cache(shp_path=args.shp_path, cache_path=args.cache_path)
    elif args.command == "geocode":
        run_geocode(
            export_path=args.export_path,
            result_path=args.result_path,
            shp_path=args.shp_path,
            cache_path=args.cache_path,
            data_dir=args.data_dir,
            sample=args.sample,
        )
