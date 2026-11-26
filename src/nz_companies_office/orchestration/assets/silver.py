"""Silver-layer assets: typed, renamed, validated, deduplicated entity tables.

Rows that fail validation (e.g. a malformed NZBN) are quarantined to a
``_rejects`` sidecar table rather than dropped or failing the whole asset —
see ``@asset_check``s in this package for the reject-rate guardrail.
"""

from pathlib import Path

import duckdb
from dagster import AssetCheckExecutionContext
from dagster import AssetCheckResult
from dagster import AssetExecutionContext
from dagster import AssetsDefinition
from dagster import asset
from dagster import asset_check
from dagster_duckdb import DuckDBResource

from nz_companies_office.config import SETTINGS
from nz_companies_office.orchestration.assets.bronze import bronze_companies_abn
from nz_companies_office.orchestration.assets.bronze import bronze_companies_address_for_service
from nz_companies_office.orchestration.assets.bronze import bronze_companies_business_industry_classification
from nz_companies_office.orchestration.assets.bronze import bronze_companies_core_data
from nz_companies_office.orchestration.assets.bronze import bronze_companies_director
from nz_companies_office.orchestration.assets.bronze import bronze_companies_gst
from nz_companies_office.orchestration.assets.bronze import bronze_companies_insolvency
from nz_companies_office.orchestration.assets.bronze import bronze_companies_public_address
from nz_companies_office.orchestration.assets.bronze import bronze_companies_registered_office_address
from nz_companies_office.orchestration.assets.bronze import bronze_companies_shareholder
from nz_companies_office.orchestration.assets.bronze import bronze_companies_trading_area
from nz_companies_office.orchestration.assets.bronze import bronze_companies_trading_name
from nz_companies_office.orchestration.assets.bronze import bronze_companies_website
from nz_companies_office.orchestration.assets.bronze import bronze_maori_business_identifier
from nz_companies_office.orchestration.assets.bronze import bronze_table_output_path
from nz_companies_office.orchestration.partitions import snapshot_month_partitions
from nz_companies_office.orchestration.sql import read_sql


def materialize_silver_company(
    conn: duckdb.DuckDBPyConnection,
    transform_sql: str,
    input_path: Path,
    month: str,
    output_path: Path,
    rejects_path: Path,
) -> tuple[int, int]:
    """Run the company transform and split valid/invalid NZBN rows into two Parquet outputs.

    Args:
        conn: Open DuckDB connection.
        transform_sql: The ``sql/silver/company.sql`` query text.
        input_path: Path to the bronze Parquet file for one snapshot month.
        month: The snapshot month (``yyyymm``) being processed.
        output_path: Destination Parquet file for valid rows.
        rejects_path: Destination Parquet file for rows with an invalid NZBN.

    Returns:
        A ``(good_row_count, rejected_row_count)`` tuple.

    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rejects_path.parent.mkdir(parents=True, exist_ok=True)
    params = {"input_path": str(input_path), "month": month}

    conn.execute(
        # transform_sql is a checked-in sql/silver/*.sql file, not user input; data values are
        # parameter-bound above via $input_path/$month/$output_path, not interpolated.
        f"COPY (SELECT * EXCLUDE (is_valid_nzbn_format) FROM ({transform_sql}) WHERE is_valid_nzbn_format) "  # noqa: S608
        "TO $output_path (FORMAT PARQUET)",
        {**params, "output_path": str(output_path)},
    )
    conn.execute(
        "COPY ("  # noqa: S608
        "SELECT nzbn AS nzbn_raw, company_number, snapshot_month, 'invalid_nzbn_format' AS reject_reason "
        f"FROM ({transform_sql}) WHERE NOT is_valid_nzbn_format"
        ") TO $rejects_path (FORMAT PARQUET)",
        {**params, "rejects_path": str(rejects_path)},
    )

    good_row = conn.execute(
        "SELECT count(*) FROM read_parquet($path, hive_partitioning = false)",
        {"path": str(output_path)},
    ).fetchone()
    reject_row = conn.execute(
        "SELECT count(*) FROM read_parquet($path, hive_partitioning = false)",
        {"path": str(rejects_path)},
    ).fetchone()
    good_count = int(good_row[0]) if good_row else 0
    reject_count = int(reject_row[0]) if reject_row else 0
    return good_count, reject_count


def silver_company_output_path(month: str) -> Path:
    """Destination Parquet path for the valid-rows silver company table."""
    return SETTINGS.silver_dir / "company" / f"snapshot_month={month}" / "part-0.parquet"


def silver_company_rejects_path(month: str) -> Path:
    """Destination Parquet path for the silver company rejects sidecar."""
    return SETTINGS.silver_dir / "company__rejects" / f"snapshot_month={month}" / "part-0.parquet"


@asset(
    partitions_def=snapshot_month_partitions,
    group_name="silver",
    deps=[bronze_companies_core_data],
)
def silver_company(context: AssetExecutionContext, duckdb: DuckDBResource) -> None:
    """Typed, renamed, validated, deduplicated ``company`` entity for one snapshot month."""
    month = context.partition_key
    input_path = SETTINGS.bronze_dir / "companies_core_data" / f"snapshot_month={month}" / "part-0.parquet"
    output_path = silver_company_output_path(month)
    rejects_path = silver_company_rejects_path(month)
    transform_sql = read_sql("silver", "company")
    with duckdb.get_connection() as conn:
        good_count, reject_count = materialize_silver_company(
            conn,
            transform_sql,
            input_path,
            month,
            output_path,
            rejects_path,
        )
    context.add_output_metadata(
        {
            "good_row_count": good_count,
            "reject_row_count": reject_count,
            "output_path": str(output_path),
        },
    )


REJECT_RATE_THRESHOLD = 0.001


def compute_reject_rate(conn: duckdb.DuckDBPyConnection, output_path: Path, rejects_path: Path) -> float:
    """Compute the fraction of rows quarantined to the rejects sidecar.

    Args:
        conn: Open DuckDB connection.
        output_path: The silver_company main output Parquet file.
        rejects_path: The silver_company rejects sidecar Parquet file.

    Returns:
        ``reject_count / (good_count + reject_count)``, or ``0.0`` if both are empty.

    """
    good_row = conn.execute(
        "SELECT count(*) FROM read_parquet($path, hive_partitioning = false)",
        {"path": str(output_path)},
    ).fetchone()
    reject_row = conn.execute(
        "SELECT count(*) FROM read_parquet($path, hive_partitioning = false)",
        {"path": str(rejects_path)},
    ).fetchone()
    good_count = int(good_row[0]) if good_row else 0
    reject_count = int(reject_row[0]) if reject_row else 0
    total = good_count + reject_count
    return reject_count / total if total else 0.0


@asset_check(asset=silver_company, partitions_def=snapshot_month_partitions)
def silver_company_reject_rate_check(context: AssetCheckExecutionContext, duckdb: DuckDBResource) -> AssetCheckResult:
    """Fail only if the NZBN reject rate for this snapshot month exceeds the threshold."""
    month = context.partition_key
    with duckdb.get_connection() as conn:
        rate = compute_reject_rate(conn, silver_company_output_path(month), silver_company_rejects_path(month))
    return AssetCheckResult(
        passed=rate <= REJECT_RATE_THRESHOLD,
        metadata={"reject_rate": rate, "threshold": REJECT_RATE_THRESHOLD},
    )


def materialize_silver_table(
    conn: duckdb.DuckDBPyConnection,
    transform_sql: str,
    output_path: Path,
    params: dict[str, str],
) -> int:
    """Run a silver transform with no reject sidecar and write the result to Parquet.

    Args:
        conn: Open DuckDB connection.
        transform_sql: A ``sql/silver/*.sql`` query text.
        output_path: Destination Parquet file. Parent directories are created.
        params: Named parameters bound into ``transform_sql`` (e.g. ``$input_path``, ``$month``).

    Returns:
        The number of rows written.

    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    conn.execute(
        f"COPY ({transform_sql}) TO $output_path (FORMAT PARQUET)",
        {**params, "output_path": str(output_path)},
    )
    row = conn.execute(
        "SELECT count(*) FROM read_parquet($path, hive_partitioning = false)",
        {"path": str(output_path)},
    ).fetchone()
    return int(row[0]) if row else 0


def silver_table_output_path(name: str, month: str) -> Path:
    """Destination Parquet path for one silver table's snapshot-month partition."""
    return SETTINGS.silver_dir / name / f"snapshot_month={month}" / "part-0.parquet"


def _make_silver_asset(name: str, bronze_table: str, bronze_asset: AssetsDefinition) -> AssetsDefinition:
    """Build a single-source, no-rejects silver asset, named ``silver_<name>``.

    The transform SQL is read from ``sql/silver/<name>.sql`` and must accept
    ``$input_path`` and ``$month`` parameters, matching the convention used by
    ``company.sql``/``shareholder.sql``/etc.
    """

    @asset(name=f"silver_{name}", partitions_def=snapshot_month_partitions, group_name="silver", deps=[bronze_asset])
    def _silver_asset(context: AssetExecutionContext, duckdb: DuckDBResource) -> None:
        month = context.partition_key
        input_path = bronze_table_output_path(bronze_table, month)
        output_path = silver_table_output_path(name, month)
        transform_sql = read_sql("silver", name)
        with duckdb.get_connection() as conn:
            row_count = materialize_silver_table(
                conn,
                transform_sql,
                output_path,
                {"input_path": str(input_path), "month": month},
            )
        context.add_output_metadata({"row_count": row_count, "output_path": str(output_path)})

    return _silver_asset


silver_shareholder = _make_silver_asset("shareholder", "companies_shareholder", bronze_companies_shareholder)
silver_director = _make_silver_asset("director", "companies_director", bronze_companies_director)
silver_company_industry = _make_silver_asset(
    "company_industry",
    "companies_business_industry_classification",
    bronze_companies_business_industry_classification,
)
silver_trading_name = _make_silver_asset("trading_name", "companies_trading_name", bronze_companies_trading_name)
silver_trading_area = _make_silver_asset("trading_area", "companies_trading_area", bronze_companies_trading_area)
silver_insolvency = _make_silver_asset("insolvency", "companies_insolvency", bronze_companies_insolvency)
silver_company_abn = _make_silver_asset("company_abn", "companies_abn", bronze_companies_abn)
silver_company_gst = _make_silver_asset("company_gst", "companies_gst", bronze_companies_gst)
silver_company_website = _make_silver_asset("company_website", "companies_website", bronze_companies_website)
silver_maori_business_identifier = _make_silver_asset(
    "maori_business_identifier",
    "maori_business_identifier",
    bronze_maori_business_identifier,
)


def materialize_silver_company_address(
    conn: duckdb.DuckDBPyConnection,
    transform_sql: str,
    reg_office_path: Path,
    service_path: Path,
    public_path: Path,
    month: str,
    output_path: Path,
) -> int:
    """Union the three company-level address sources into one conformed silver table.

    Args:
        conn: Open DuckDB connection.
        transform_sql: The ``sql/silver/company_address.sql`` query text.
        reg_office_path: Bronze Parquet for ``companies_registered_office_address``.
        service_path: Bronze Parquet for ``companies_address_for_service``.
        public_path: Bronze Parquet for ``companies_public_address``.
        month: The snapshot month (``yyyymm``) being processed.
        output_path: Destination Parquet file.

    Returns:
        The number of rows written.

    """
    return materialize_silver_table(
        conn,
        transform_sql,
        output_path,
        {
            "input_reg_office": str(reg_office_path),
            "input_service": str(service_path),
            "input_public": str(public_path),
            "month": month,
        },
    )


@asset(
    partitions_def=snapshot_month_partitions,
    group_name="silver",
    deps=[
        bronze_companies_registered_office_address,
        bronze_companies_address_for_service,
        bronze_companies_public_address,
    ],
)
def silver_company_address(context: AssetExecutionContext, duckdb: DuckDBResource) -> None:
    """Conformed, deduplicated company address table, unioning all three address sources."""
    month = context.partition_key
    reg_office_path = bronze_table_output_path("companies_registered_office_address", month)
    service_path = bronze_table_output_path("companies_address_for_service", month)
    public_path = bronze_table_output_path("companies_public_address", month)
    output_path = silver_table_output_path("company_address", month)
    transform_sql = read_sql("silver", "company_address")
    with duckdb.get_connection() as conn:
        row_count = materialize_silver_company_address(
            conn,
            transform_sql,
            reg_office_path,
            service_path,
            public_path,
            month,
            output_path,
        )
    context.add_output_metadata({"row_count": row_count, "output_path": str(output_path)})
