"""Shared DuckDB query helpers for marimo medallion-layer evaluation notebooks.

Reuses the same path-resolution functions the Dagster assets use
(`src/nz_companies_office/orchestration/assets/*.py`), so this notebook can't
drift from where the pipeline actually reads/writes.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import duckdb
import marimo as mo

if TYPE_CHECKING:
    import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nz_companies_office.orchestration.assets.bronze import bronze_table_output_path
from nz_companies_office.orchestration.assets.gold import gold_dim_output_path
from nz_companies_office.orchestration.assets.gold import gold_fact_output_path
from nz_companies_office.orchestration.assets.gold import silver_table_glob
from nz_companies_office.orchestration.assets.silver import silver_company_output_path
from nz_companies_office.orchestration.assets.silver import silver_company_rejects_path
from nz_companies_office.orchestration.partitions import snapshot_month_partitions

_conn = duckdb.connect(":memory:")


def available_months() -> list[str]:
    """Snapshot months with materialized data on disk, sorted ascending."""
    return sorted(snapshot_month_partitions.get_partition_keys())


def bronze_glob(table: str) -> str:
    """Glob matching every materialized partition of one bronze table."""
    return str(bronze_table_output_path(table, "*"))


def silver_glob(table: str) -> str:
    """Glob matching every materialized partition of one silver table."""
    return silver_table_glob(table)


def gold_dim_path(name: str) -> str:
    """Path to one (unpartitioned) gold dimension table."""
    return str(gold_dim_output_path(name))


def gold_fact_glob(name: str) -> str:
    """Glob matching every materialized partition of one gold fact table."""
    return str(gold_fact_output_path(name, "*"))


def silver_company_glob() -> str:
    """Glob matching every materialized silver_company partition."""
    return str(silver_company_output_path("*"))


def silver_company_rejects_glob() -> str:
    """Glob matching every materialized silver_company__rejects partition."""
    return str(silver_company_rejects_path("*"))


def query(sql: str) -> pl.DataFrame:
    """Run a DuckDB SQL query against the medallion layers, returning a polars DataFrame."""
    return _conn.execute(sql).pl()


def row_count(glob_or_path: str) -> int:
    """Row count of a Parquet file or glob, or 0 if nothing matches."""
    try:
        sql = f"SELECT count(*) AS n FROM read_parquet('{glob_or_path}', hive_partitioning = false)"
        return int(query(sql)["n"][0])
    except duckdb.IOException:
        return 0


def mo_table(sql: str, **kwargs: object) -> mo.ui.table | mo.Html:
    """Run a query and render it as a marimo table, or a placeholder if empty."""
    df = query(sql)
    if len(df) == 0:
        return mo.md("*No results*")
    return mo.ui.table(df, **kwargs)
