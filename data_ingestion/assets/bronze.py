"""Bronze-layer assets: 1:1 schema-preserving copies of raw NZBN CSV exports to Parquet.

No renaming, typing, or filtering happens here — every column is read as
``VARCHAR`` so the bronze Parquet file is a durable, columnar, queryable copy
of exactly what landed in ``data/raw/``.
"""

from pathlib import Path

import duckdb
from dagster import AssetExecutionContext
from dagster import AssetsDefinition
from dagster import asset
from dagster_duckdb import DuckDBResource

from data_ingestion.partitions import snapshot_month_partitions
from data_ingestion.sql import read_sql
from nz_companies_office.config import SETTINGS


def materialize_bronze_table(
    conn: duckdb.DuckDBPyConnection,
    select_sql: str,
    input_path: Path,
    output_path: Path,
) -> int:
    """Run a bronze SELECT against a raw CSV and write the result to Parquet.

    Args:
        conn: Open DuckDB connection.
        select_sql: A ``SELECT ... FROM read_csv($input_path, ...)`` query.
        input_path: Path to the source CSV for one snapshot month.
        output_path: Destination Parquet file path. Parent directories are created.

    Returns:
        The number of rows written.

    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    conn.execute(
        f"COPY ({select_sql}) TO $output_path (FORMAT PARQUET)",
        {"input_path": str(input_path), "output_path": str(output_path)},
    )
    result = conn.execute("SELECT count(*) FROM read_parquet($output_path)", {"output_path": str(output_path)})
    row = result.fetchone()
    return int(row[0]) if row else 0


def bronze_table_output_path(table: str, month: str) -> Path:
    """Destination Parquet path for one bronze table's snapshot-month partition."""
    return SETTINGS.bronze_dir / table / f"snapshot_month={month}" / "part-0.parquet"


def _make_bronze_asset(table: str, csv_filename: str) -> AssetsDefinition:
    """Build a bronze asset for one source CSV, named ``bronze_<table>``."""

    @asset(name=f"bronze_{table}", partitions_def=snapshot_month_partitions, group_name="bronze")
    def _bronze_asset(context: AssetExecutionContext, duckdb: DuckDBResource) -> None:
        month = context.partition_key
        input_path = SETTINGS.raw_data_dir / month / csv_filename
        output_path = bronze_table_output_path(table, month)
        select_sql = read_sql("bronze", table)
        with duckdb.get_connection() as conn:
            row_count = materialize_bronze_table(conn, select_sql, input_path, output_path)
        context.add_output_metadata({"row_count": row_count, "output_path": str(output_path)})

    return _bronze_asset


bronze_companies_core_data = _make_bronze_asset("companies_core_data", "companies_core_data.csv")
bronze_companies_shareholder = _make_bronze_asset("companies_shareholder", "companies_shareholder.csv")
bronze_companies_director = _make_bronze_asset("companies_director", "companies_director.csv")
bronze_companies_registered_office_address = _make_bronze_asset(
    "companies_registered_office_address",
    "companies_registered_office_address.csv",
)
bronze_companies_address_for_service = _make_bronze_asset(
    "companies_address_for_service",
    "companies_address_for_service.csv",
)
bronze_companies_public_address = _make_bronze_asset("companies_public_address", "companies_public_address.csv")
bronze_companies_business_industry_classification = _make_bronze_asset(
    "companies_business_industry_classification",
    "companies_business_industry_classification.csv",
)
bronze_companies_trading_name = _make_bronze_asset("companies_trading_name", "companies_trading_name.csv")
bronze_companies_trading_area = _make_bronze_asset("companies_trading_area", "companies_trading_area.csv")
bronze_companies_insolvency = _make_bronze_asset("companies_insolvency", "companies_insolvency.csv")
bronze_companies_abn = _make_bronze_asset("companies_abn", "companies_abn.csv")
bronze_companies_gst = _make_bronze_asset("companies_gst", "companies_gst.csv")
bronze_companies_website = _make_bronze_asset("companies_website", "companies_website.csv")
bronze_maori_business_identifier = _make_bronze_asset("maori_business_identifier", "maori_business_identifier.csv")
