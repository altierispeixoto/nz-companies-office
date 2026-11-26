"""Gold-layer assets: current-state dimensions and SCD2-style change-fact tables.

Dimension assets are unpartitioned and always recompute from all available
silver history (latest snapshot month wins per key). Fact assets are
partitioned by snapshot month and read the current and previous silver
partition explicitly, rather than fighting Dagster's ``PartitionMapping``
API for this non-time-window case.
"""

from pathlib import Path

import duckdb
from dagster import AssetExecutionContext
from dagster import asset
from dagster_duckdb import DuckDBResource

from nz_companies_office.config import SETTINGS
from nz_companies_office.orchestration.assets.silver import silver_company
from nz_companies_office.orchestration.sql import read_sql


def materialize_gold_company_dim(
    conn: duckdb.DuckDBPyConnection,
    select_sql: str,
    silver_glob: str,
    output_path: Path,
) -> int:
    """Recompute the current-state company dimension from all silver history.

    Args:
        conn: Open DuckDB connection.
        select_sql: The ``sql/gold/dims/company_dim.sql`` query text.
        silver_glob: Glob pattern matching every ``silver_company`` partition's Parquet file.
        output_path: Destination Parquet file (overwritten each run).

    Returns:
        The number of rows written (one per distinct ``nzbn``).

    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    conn.execute(
        f"COPY ({select_sql}) TO $output_path (FORMAT PARQUET)",
        {"silver_glob": silver_glob, "output_path": str(output_path)},
    )
    row = conn.execute(
        "SELECT count(*) FROM read_parquet($path, hive_partitioning = false)",
        {"path": str(output_path)},
    ).fetchone()
    return int(row[0]) if row else 0


def silver_company_glob() -> str:
    """Glob pattern matching every existing silver_company partition."""
    return str(SETTINGS.silver_dir / "company" / "snapshot_month=*" / "part-0.parquet")


def gold_company_dim_output_path() -> Path:
    """Destination Parquet path for the current-state company dimension."""
    return SETTINGS.gold_dir / "dims" / "company_dim" / "part-0.parquet"


@asset(group_name="gold_dims", deps=[silver_company])
def gold_company_dim(context: AssetExecutionContext, duckdb: DuckDBResource) -> None:
    """Current-state company dimension: one row per nzbn, latest snapshot month wins."""
    select_sql = read_sql("gold", "dims", "company_dim")
    output_path = gold_company_dim_output_path()
    with duckdb.get_connection() as conn:
        row_count = materialize_gold_company_dim(conn, select_sql, silver_company_glob(), output_path)
    context.add_output_metadata({"row_count": row_count, "output_path": str(output_path)})
