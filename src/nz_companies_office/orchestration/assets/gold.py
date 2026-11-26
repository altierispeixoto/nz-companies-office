"""Gold-layer assets: current-state dimensions and SCD2-style change-fact tables.

Dimension assets are unpartitioned and always recompute from all available
silver history (latest snapshot month wins per key). Fact assets are
partitioned by snapshot month and read the current and previous silver
partition explicitly, rather than fighting Dagster's ``PartitionMapping``
API for this non-time-window case.
"""

import shutil
from collections.abc import Sequence
from pathlib import Path

import duckdb
from dagster import AssetCheckResult
from dagster import AssetExecutionContext
from dagster import AssetsDefinition
from dagster import asset
from dagster import asset_check
from dagster_duckdb import DuckDBResource

from nz_companies_office.config import SETTINGS
from nz_companies_office.orchestration.assets.silver import silver_company
from nz_companies_office.orchestration.assets.silver import silver_company_abn
from nz_companies_office.orchestration.assets.silver import silver_company_address
from nz_companies_office.orchestration.assets.silver import silver_company_gst
from nz_companies_office.orchestration.assets.silver import silver_company_industry
from nz_companies_office.orchestration.assets.silver import silver_company_output_path
from nz_companies_office.orchestration.assets.silver import silver_company_website
from nz_companies_office.orchestration.assets.silver import silver_director
from nz_companies_office.orchestration.assets.silver import silver_insolvency
from nz_companies_office.orchestration.assets.silver import silver_maori_business_identifier
from nz_companies_office.orchestration.assets.silver import silver_shareholder
from nz_companies_office.orchestration.assets.silver import silver_table_output_path
from nz_companies_office.orchestration.assets.silver import silver_trading_area
from nz_companies_office.orchestration.assets.silver import silver_trading_name
from nz_companies_office.orchestration.partitions import snapshot_month_partitions
from nz_companies_office.orchestration.sql import read_sql


def materialize_gold_table(
    conn: duckdb.DuckDBPyConnection,
    select_sql: str,
    output_path: Path,
    params: dict[str, str],
) -> int:
    """Run a gold SELECT (dimension or fact) and write the result to Parquet.

    Args:
        conn: Open DuckDB connection.
        select_sql: A ``sql/gold/{dims,facts}/*.sql`` query text.
        output_path: Destination Parquet file. Parent directories are created.
        params: Named parameters bound into ``select_sql`` (e.g. ``$silver_glob``).

    Returns:
        The number of rows written.

    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    conn.execute(
        f"COPY ({select_sql}) TO $output_path (FORMAT PARQUET)",
        {**params, "output_path": str(output_path)},
    )
    row = conn.execute(
        "SELECT count(*) FROM read_parquet($path, hive_partitioning = false)",
        {"path": str(output_path)},
    ).fetchone()
    return int(row[0]) if row else 0


def silver_table_glob(name: str) -> str:
    """Glob pattern matching every existing partition of one silver table."""
    return str(SETTINGS.silver_dir / name / "snapshot_month=*" / "part-0.parquet")


def gold_dim_output_path(name: str) -> Path:
    """Destination Parquet path for one current-state gold dimension table."""
    return SETTINGS.gold_dir / "dims" / name / "part-0.parquet"


def gold_company_dim_output_path() -> Path:
    """Destination Parquet path for the current-state company dimension."""
    return gold_dim_output_path("company_dim")


@asset(
    group_name="gold_dims",
    deps=[
        silver_company,
        silver_company_abn,
        silver_company_gst,
        silver_company_website,
        silver_maori_business_identifier,
    ],
)
def gold_company_dim(context: AssetExecutionContext, duckdb: DuckDBResource) -> None:
    """Current-state company dimension: one row per nzbn, latest snapshot month wins.

    Folds in abn/gst/website/maori_business_identifier as extra columns -- these were
    simple per-company SET statements in scripts/csv/08_properties.cypher (no business
    logic to migrate), so they don't need their own dimension table.
    """
    select_sql = read_sql("gold", "dims", "company_dim")
    output_path = gold_company_dim_output_path()
    params = {
        "silver_glob": silver_table_glob("company"),
        "abn_glob": silver_table_glob("company_abn"),
        "gst_glob": silver_table_glob("company_gst"),
        "website_glob": silver_table_glob("company_website"),
        "maori_glob": silver_table_glob("maori_business_identifier"),
    }
    with duckdb.get_connection() as conn:
        row_count = materialize_gold_table(conn, select_sql, output_path, params)
    context.add_output_metadata({"row_count": row_count, "output_path": str(output_path)})


def _make_gold_dim_asset(name: str, silver_table: str, silver_asset: AssetsDefinition) -> AssetsDefinition:
    """Build a single-source, current-state gold dimension asset, named ``gold_<name>``.

    The transform SQL is read from ``sql/gold/dims/<name>.sql`` and must accept a
    ``$silver_glob`` parameter matching every partition of one silver table.
    """

    @asset(name=f"gold_{name}", group_name="gold_dims", deps=[silver_asset])
    def _gold_dim_asset(context: AssetExecutionContext, duckdb: DuckDBResource) -> None:
        select_sql = read_sql("gold", "dims", name)
        output_path = gold_dim_output_path(name)
        with duckdb.get_connection() as conn:
            row_count = materialize_gold_table(
                conn,
                select_sql,
                output_path,
                {"silver_glob": silver_table_glob(silver_table)},
            )
        context.add_output_metadata({"row_count": row_count, "output_path": str(output_path)})

    return _gold_dim_asset


gold_shareholding = _make_gold_dim_asset("shareholding", "shareholder", silver_shareholder)
gold_director_dim = _make_gold_dim_asset("director_dim", "director", silver_director)
gold_company_industry = _make_gold_dim_asset("company_industry", "company_industry", silver_company_industry)
gold_company_trading_name = _make_gold_dim_asset("company_trading_name", "trading_name", silver_trading_name)
gold_company_trading_area = _make_gold_dim_asset("company_trading_area", "trading_area", silver_trading_area)
gold_company_insolvency = _make_gold_dim_asset("company_insolvency", "insolvency", silver_insolvency)
gold_address_dim = _make_gold_dim_asset("address_dim", "company_address", silver_company_address)
gold_company_address = _make_gold_dim_asset("company_address", "company_address", silver_company_address)


def count_duplicate_nzbn(conn: duckdb.DuckDBPyConnection, path: Path) -> int:
    """Count how many distinct nzbn values appear more than once in a Parquet file.

    Args:
        conn: Open DuckDB connection.
        path: Parquet file expected to have at most one row per nzbn.

    Returns:
        The number of nzbn values with more than one row.

    """
    row = conn.execute(
        "SELECT count(*) FROM ("
        "SELECT nzbn FROM read_parquet($path, hive_partitioning = false) "
        "GROUP BY nzbn HAVING count(*) > 1"
        ")",
        {"path": str(path)},
    ).fetchone()
    return int(row[0]) if row else 0


@asset_check(asset=gold_company_dim)
def gold_company_dim_uniqueness_check(duckdb: DuckDBResource) -> AssetCheckResult:
    """Fail if gold_company_dim contains more than one row for the same nzbn."""
    with duckdb.get_connection() as conn:
        duplicate_count = count_duplicate_nzbn(conn, gold_company_dim_output_path())
    return AssetCheckResult(passed=duplicate_count == 0, metadata={"duplicate_count": duplicate_count})


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


def gold_fact_output_path(name: str, month: str) -> Path:
    """Destination Parquet path for one partition of a gold SCD2 fact table."""
    return SETTINGS.gold_dir / "facts" / name / f"snapshot_month={month}" / "part-0.parquet"


def _make_gold_fact_asset(name: str, silver_table: str, silver_asset: AssetsDefinition) -> AssetsDefinition:
    """Build a month-over-month SCD2 change-fact asset, named ``gold_<name>``.

    The transform SQL is read from ``sql/gold/facts/<name>.sql`` and must accept
    ``$current_path``, ``$previous_path``, and ``$month`` parameters, matching the
    convention used by ``company_status_changes.sql``. When no previous month exists
    (the earliest partition), ``$previous_path`` equals ``$current_path`` -- comparing
    a snapshot against itself always yields zero change rows.
    """

    @asset(
        name=f"gold_{name}",
        partitions_def=snapshot_month_partitions,
        group_name="gold_facts",
        deps=[silver_asset],
    )
    def _gold_fact_asset(context: AssetExecutionContext, duckdb: DuckDBResource) -> None:
        month = context.partition_key
        current_path = silver_table_output_path(silver_table, month)
        previous_month = previous_partition_key(month, snapshot_month_partitions.get_partition_keys())
        previous_path = silver_table_output_path(silver_table, previous_month) if previous_month else current_path
        output_path = gold_fact_output_path(name, month)
        select_sql = read_sql("gold", "facts", name)
        with duckdb.get_connection() as conn:
            row_count = materialize_gold_table(
                conn,
                select_sql,
                output_path,
                {"current_path": str(current_path), "previous_path": str(previous_path), "month": month},
            )
        context.add_output_metadata(
            {
                "row_count": row_count,
                "output_path": str(output_path),
                "previous_snapshot_month": previous_month or "",
            },
        )

    return _gold_fact_asset


gold_shareholding_changes = _make_gold_fact_asset("shareholding_changes", "shareholder", silver_shareholder)
gold_director_appointment_changes = _make_gold_fact_asset(
    "director_appointment_changes",
    "director",
    silver_director,
)


def materialize_gold_export_csv(
    conn: duckdb.DuckDBPyConnection,
    select_sql: str,
    input_path: Path,
    output_path: Path,
) -> int:
    """Flatten a gold dimension Parquet file into a CSV for Neo4j's LOAD CSV.

    Args:
        conn: Open DuckDB connection.
        select_sql: A query that renames gold columns to the header the target
            ``.cypher`` script expects.
        input_path: The gold dimension's Parquet file.
        output_path: Destination CSV file (with header).

    Returns:
        The number of data rows written.

    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    conn.execute(
        f"COPY ({select_sql}) TO $output_path (FORMAT CSV, HEADER)",
        {"input_path": str(input_path), "output_path": str(output_path)},
    )
    row = conn.execute(
        "SELECT count(*) FROM read_csv($path, header = true, all_varchar = true)",
        {"path": str(output_path)},
    ).fetchone()
    return int(row[0]) if row else 0


def gold_export_companies_csv_output_path(month: str) -> Path:
    """Destination CSV path for the Neo4j-bound company export for one snapshot month.

    Each month gets its own export directory (rather than a fixed ``latest/``) because the
    official Neo4j Docker image's entrypoint recursively chowns any bind-mounted directory to
    its internal user the first time a container starts against it, making it unwritable from
    the host afterward -- see the comment in docker-compose.yml. Reusing a directory a Neo4j
    container has already mounted would fail on the next pipeline run.
    """
    return SETTINGS.gold_dir / "_neo4j_export" / month / "companies_core_data.csv"


# Only companies_core_data.csv is sourced from gold so far (this increment). The other 13 files
# scripts/csv/*.cypher reads haven't been migrated through the medallion pipeline yet (see
# Increment 2 in .specs/features/medallion-architecture/tasks.md), so they're copied through
# unchanged from the latest raw snapshot month to keep `just load-db` fully working in the
# meantime -- the Docker mount now points at the export dir, not data/raw/, for all 14 steps.
PASSTHROUGH_RAW_FILES = (
    "companies_director.csv",
    "companies_shareholder.csv",
    "companies_registered_office_address.csv",
    "companies_address_for_service.csv",
    "companies_public_address.csv",
    "companies_business_industry_classification.csv",
    "companies_trading_name.csv",
    "companies_trading_area.csv",
    "companies_insolvency.csv",
    "companies_abn.csv",
    "companies_gst.csv",
    "companies_website.csv",
    "maori_business_identifier.csv",
)


def copy_passthrough_raw_files(source_month_dir: Path, export_dir: Path) -> list[str]:
    """Copy not-yet-migrated raw CSVs into the Neo4j export directory unchanged.

    Args:
        source_month_dir: Raw data directory for the month to copy from (typically the
            latest available snapshot month).
        export_dir: The Neo4j import directory to copy into.

    Returns:
        The filenames actually copied; a missing source file is skipped, not an error.

    """
    export_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for filename in PASSTHROUGH_RAW_FILES:
        source = source_month_dir / filename
        if source.exists():
            shutil.copy(source, export_dir / filename)
            copied.append(filename)
    return copied


@asset(group_name="gold_export", deps=[gold_company_dim])
def gold_export_companies_csv(context: AssetExecutionContext, duckdb: DuckDBResource) -> None:
    """Flat CSV export of gold_company_dim, feeding scripts/csv/01_companies.cypher.

    Also copies the other 13 not-yet-migrated raw CSVs scripts/csv/*.cypher reads, from the
    latest available snapshot month, so the full load-db pipeline keeps working end-to-end.
    """
    latest_month = max(snapshot_month_partitions.get_partition_keys())
    select_sql = read_sql("gold", "export", "companies_core_data")
    output_path = gold_export_companies_csv_output_path(latest_month)
    with duckdb.get_connection() as conn:
        row_count = materialize_gold_export_csv(conn, select_sql, gold_company_dim_output_path(), output_path)
    copied = copy_passthrough_raw_files(SETTINGS.raw_data_dir / latest_month, output_path.parent)
    context.add_output_metadata(
        {
            "row_count": row_count,
            "output_path": str(output_path),
            "passthrough_files_copied": len(copied),
        },
    )
