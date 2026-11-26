"""Bronze-layer assets: 1:1 schema-preserving copies of raw NZBN CSV exports to Parquet.

No renaming, typing, or filtering happens here — every column is read as
``VARCHAR`` so the bronze Parquet file is a durable, columnar, queryable copy
of exactly what landed in ``data/raw/``.
"""

from pathlib import Path

import duckdb
from dagster import AssetExecutionContext
from dagster import asset
from dagster_duckdb import DuckDBResource

from nz_companies_office.config import SETTINGS
from nz_companies_office.orchestration.partitions import snapshot_month_partitions
from nz_companies_office.orchestration.sql import read_sql


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


@asset(partitions_def=snapshot_month_partitions, group_name="bronze")
def bronze_companies_core_data(context: AssetExecutionContext, duckdb: DuckDBResource) -> None:
    """Bronze copy of ``companies_core_data.csv`` for one snapshot month."""
    month = context.partition_key
    input_path = SETTINGS.raw_data_dir / month / "companies_core_data.csv"
    output_path = SETTINGS.bronze_dir / "companies_core_data" / f"snapshot_month={month}" / "part-0.parquet"
    select_sql = read_sql("bronze", "companies_core_data")
    with duckdb.get_connection() as conn:
        row_count = materialize_bronze_table(conn, select_sql, input_path, output_path)
    context.add_output_metadata({"row_count": row_count, "output_path": str(output_path)})
