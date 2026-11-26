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


def export_output_path(month: str, filename: str) -> Path:
    """Destination path for one Neo4j-bound export CSV for a snapshot month.

    Each month gets its own export directory (rather than a fixed ``latest/``) because the
    official Neo4j Docker image's entrypoint recursively chowns any bind-mounted directory to
    its internal user the first time a container starts against it, making it unwritable from
    the host afterward -- see the comment in docker-compose.yml. Reusing a directory a Neo4j
    container has already mounted would fail on the next pipeline run.
    """
    return SETTINGS.gold_dir / "_neo4j_export" / month / filename


def gold_export_companies_csv_output_path(month: str) -> Path:
    """Destination CSV path for the Neo4j-bound company export for one snapshot month."""
    return export_output_path(month, "companies_core_data.csv")


def materialize_gold_export_csv_multi(
    conn: duckdb.DuckDBPyConnection,
    select_sql: str,
    output_path: Path,
    params: dict[str, str],
) -> int:
    """Like ``materialize_gold_export_csv``, for exports joining more than one gold table.

    Args:
        conn: Open DuckDB connection.
        select_sql: A query that renames gold columns to the header the target
            ``.cypher`` script expects.
        output_path: Destination CSV file (with header).
        params: Named parameters bound into ``select_sql`` (e.g. multiple ``$*_path`` globs).

    Returns:
        The number of data rows written.

    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    conn.execute(
        f"COPY ({select_sql}) TO $output_path (FORMAT CSV, HEADER)",
        {**params, "output_path": str(output_path)},
    )
    row = conn.execute(
        "SELECT count(*) FROM read_csv($path, header = true, all_varchar = true)",
        {"path": str(output_path)},
    ).fetchone()
    return int(row[0]) if row else 0


def _make_gold_export_asset(name: str, csv_filename: str, gold_asset: AssetsDefinition) -> AssetsDefinition:
    """Build a single-input export asset, named ``gold_export_<name>``.

    The export SQL is read from ``sql/gold/export/<name>.sql`` and must accept an
    ``$input_path`` parameter pointing at one gold dimension's Parquet file.
    """

    @asset(name=f"gold_export_{name}", group_name="gold_export", deps=[gold_asset])
    def _gold_export_asset(context: AssetExecutionContext, duckdb: DuckDBResource) -> None:
        latest_month = max(snapshot_month_partitions.get_partition_keys())
        select_sql = read_sql("gold", "export", name)
        output_path = export_output_path(latest_month, csv_filename)
        with duckdb.get_connection() as conn:
            row_count = materialize_gold_export_csv(conn, select_sql, gold_dim_output_path(name), output_path)
        context.add_output_metadata({"row_count": row_count, "output_path": str(output_path)})

    return _gold_export_asset


gold_export_companies_core_data = _make_gold_export_asset(
    "companies_core_data",
    "companies_core_data.csv",
    gold_company_dim,
)
gold_export_companies_director = _make_gold_export_asset(
    "companies_director",
    "companies_director.csv",
    gold_director_dim,
)
gold_export_companies_business_industry_classification = _make_gold_export_asset(
    "companies_business_industry_classification",
    "companies_business_industry_classification.csv",
    gold_company_industry,
)
gold_export_companies_trading_name = _make_gold_export_asset(
    "companies_trading_name",
    "companies_trading_name.csv",
    gold_company_trading_name,
)
gold_export_companies_trading_area = _make_gold_export_asset(
    "companies_trading_area",
    "companies_trading_area.csv",
    gold_company_trading_area,
)
gold_export_companies_insolvency = _make_gold_export_asset(
    "companies_insolvency",
    "companies_insolvency.csv",
    gold_company_insolvency,
)


@asset(group_name="gold_export", deps=[gold_shareholding])
def gold_export_companies_shareholder(context: AssetExecutionContext, duckdb: DuckDBResource) -> None:
    """Flat CSV export of gold_shareholding, feeding scripts/csv/03_shareholders.cypher.

    Joins back against the full silver_shareholder history to pick one representative
    row per (nzbn, shareholder_name) for the per-parcel fields (start_date, sh_status,
    parcel_id, assignment_id, address) that gold_shareholding's share-total aggregation
    doesn't preserve -- see sql/gold/export/companies_shareholder.sql.
    """
    latest_month = max(snapshot_month_partitions.get_partition_keys())
    select_sql = read_sql("gold", "export", "companies_shareholder")
    output_path = export_output_path(latest_month, "companies_shareholder.csv")
    with duckdb.get_connection() as conn:
        row_count = materialize_gold_export_csv_multi(
            conn,
            select_sql,
            output_path,
            {
                "gold_path": str(gold_dim_output_path("shareholding")),
                "silver_glob": silver_table_glob("shareholder"),
            },
        )
    context.add_output_metadata({"row_count": row_count, "output_path": str(output_path)})


@asset(group_name="gold_export", deps=[gold_company_address, gold_address_dim])
def gold_export_company_address(context: AssetExecutionContext, duckdb: DuckDBResource) -> None:
    """Flat CSV export unioning all company address types, feeding scripts/csv/04_company_address.cypher."""
    latest_month = max(snapshot_month_partitions.get_partition_keys())
    select_sql = read_sql("gold", "export", "company_address")
    output_path = export_output_path(latest_month, "companies_company_address.csv")
    with duckdb.get_connection() as conn:
        row_count = materialize_gold_export_csv_multi(
            conn,
            select_sql,
            output_path,
            {
                "company_address_path": str(gold_dim_output_path("company_address")),
                "address_dim_path": str(gold_dim_output_path("address_dim")),
            },
        )
    context.add_output_metadata({"row_count": row_count, "output_path": str(output_path)})
