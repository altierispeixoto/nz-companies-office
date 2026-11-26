"""Gold-layer assets: current-state dimensions and SCD2-style change-fact tables.

Dimension assets are unpartitioned and always recompute from all available
silver history (latest snapshot month wins per key). Fact assets are
partitioned by snapshot month and read the current and previous silver
partition explicitly, rather than fighting Dagster's ``PartitionMapping``
API for this non-time-window case.
"""

from collections.abc import Sequence
from pathlib import Path

import duckdb
from dagster import AssetExecutionContext
from dagster import asset
from dagster_duckdb import DuckDBResource

from nz_companies_office.config import SETTINGS
from nz_companies_office.orchestration.assets.silver import silver_company
from nz_companies_office.orchestration.assets.silver import silver_company_output_path
from nz_companies_office.orchestration.partitions import snapshot_month_partitions
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


def materialize_gold_company_status_changes(
    conn: duckdb.DuckDBPyConnection,
    select_sql: str,
    current_path: Path,
    previous_path: Path,
    month: str,
    output_path: Path,
) -> int:
    """Detect company status changes between two consecutive silver snapshot months.

    When no previous month exists (the earliest available partition), callers pass
    ``previous_path == current_path``: comparing a snapshot against itself always
    yields zero change rows (every status trivially equals itself), which is the
    documented behaviour for that edge case, without any special-case SQL.

    Args:
        conn: Open DuckDB connection.
        select_sql: The ``sql/gold/facts/company_status_changes.sql`` query text.
        current_path: Path to the silver_company Parquet file for ``month``.
        previous_path: Path to the silver_company Parquet file for the prior month.
        month: The snapshot month (``yyyymm``) being processed (the detection month).
        output_path: Destination Parquet file for this partition.

    Returns:
        The number of change rows written.

    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    conn.execute(
        f"COPY ({select_sql}) TO $output_path (FORMAT PARQUET)",
        {
            "current_path": str(current_path),
            "previous_path": str(previous_path),
            "month": month,
            "output_path": str(output_path),
        },
    )
    row = conn.execute(
        "SELECT count(*) FROM read_parquet($path, hive_partitioning = false)",
        {"path": str(output_path)},
    ).fetchone()
    return int(row[0]) if row else 0


def previous_partition_key(month: str, available_months: Sequence[str]) -> str | None:
    """Find the snapshot month immediately before ``month`` in a sorted list of partitions.

    Args:
        month: A snapshot month present in ``available_months``.
        available_months: All known snapshot-month partition keys (any order).

    Returns:
        The prior month, or ``None`` if ``month`` is the earliest available partition.

    """
    keys = sorted(available_months)
    idx = keys.index(month)
    return keys[idx - 1] if idx > 0 else None


def gold_company_status_changes_output_path(month: str) -> Path:
    """Destination Parquet path for one partition of the company status changes fact table."""
    return SETTINGS.gold_dir / "facts" / "company_status_changes" / f"snapshot_month={month}" / "part-0.parquet"


@asset(partitions_def=snapshot_month_partitions, group_name="gold_facts", deps=[silver_company])
def gold_company_status_changes(context: AssetExecutionContext, duckdb: DuckDBResource) -> None:
    """Company status changes detected between this snapshot month and the prior one."""
    month = context.partition_key
    current_path = silver_company_output_path(month)
    previous_month = previous_partition_key(month, snapshot_month_partitions.get_partition_keys())
    previous_path = silver_company_output_path(previous_month) if previous_month else current_path
    output_path = gold_company_status_changes_output_path(month)
    select_sql = read_sql("gold", "facts", "company_status_changes")
    with duckdb.get_connection() as conn:
        row_count = materialize_gold_company_status_changes(
            conn,
            select_sql,
            current_path,
            previous_path,
            month,
            output_path,
        )
    context.add_output_metadata(
        {
            "row_count": row_count,
            "output_path": str(output_path),
            "previous_snapshot_month": previous_month or "",
        },
    )
