"""Tests for silver-layer medallion assets."""

from __future__ import annotations

import datetime
from pathlib import Path

import duckdb

from data_ingestion.assets.bronze import materialize_bronze_table
from data_ingestion.assets.silver import materialize_silver_company
from data_ingestion.sql import read_sql

_BRONZE_FIXTURE = "tests/fixtures/raw/companies_core_data.csv"
_VALID_ROW_COUNT = 3


def _make_bronze_fixture(tmp_path: Path, conn: duckdb.DuckDBPyConnection) -> Path:
    """Materialize the shared bronze fixture CSV into a temp Parquet file."""
    bronze_sql = read_sql("bronze", "companies_core_data")
    bronze_path = tmp_path / "bronze.parquet"
    materialize_bronze_table(conn, bronze_sql, Path(_BRONZE_FIXTURE), bronze_path)
    return bronze_path


class TestMaterializeSilverCompany:
    """Tests for materialize_silver_company using the real sql/silver/company.sql transform."""

    def test_valid_rows_are_typed_and_renamed(self, tmp_path: Path) -> None:
        """Valid rows get snake_case columns and parsed dates."""
        conn = duckdb.connect(":memory:")
        try:
            bronze_path = _make_bronze_fixture(tmp_path, conn)
            output_path = tmp_path / "silver.parquet"
            rejects_path = tmp_path / "rejects.parquet"
            transform_sql = read_sql("silver", "company")
            good_count, reject_count = materialize_silver_company(
                conn,
                transform_sql,
                bronze_path,
                "202611",
                output_path,
                rejects_path,
            )
            rows = conn.execute(
                "SELECT nzbn, company_number, entity_name, incorporation_date, removal_date, snapshot_month "
                "FROM read_parquet($path, hive_partitioning = false) ORDER BY company_number",
                {"path": str(output_path)},
            ).fetchall()
        finally:
            conn.close()

        assert good_count == _VALID_ROW_COUNT
        assert reject_count == 0
        assert rows[0][1] == "3301188"
        assert rows[0][3] == datetime.date(2011, 3, 9)
        assert rows[0][4] == datetime.date(2012, 11, 20)
        assert rows[0][5] == "202611"

    def test_missing_removal_date_is_null(self, tmp_path: Path) -> None:
        """An empty REMOVAL_DATE becomes NULL, not an error or a zero-date."""
        conn = duckdb.connect(":memory:")
        try:
            bronze_path = _make_bronze_fixture(tmp_path, conn)
            output_path = tmp_path / "silver.parquet"
            rejects_path = tmp_path / "rejects.parquet"
            transform_sql = read_sql("silver", "company")
            materialize_silver_company(conn, transform_sql, bronze_path, "202611", output_path, rejects_path)
            removal_date = conn.execute(
                "SELECT removal_date FROM read_parquet($path, hive_partitioning = false) WHERE company_number = '3405451'",
                {"path": str(output_path)},
            ).fetchone()
        finally:
            conn.close()
        assert removal_date is not None
        assert removal_date[0] is None

    def test_invalid_nzbn_is_quarantined_not_dropped(self, tmp_path: Path) -> None:
        """A row with a malformed NZBN lands in the rejects sidecar, not the main table."""
        bad_csv = tmp_path / "companies_core_data.csv"
        bad_csv.write_text(
            "NZBN,COMPANY_IDENTIFIER,ENTITY_NAME,REGISTRATION_DATE,REMOVAL_DATE,ENTITY_TYPE,ENTITY_STATUS\n"
            "9429031075473,3405451,PARROT ANALYTICS LIMITED,01/06/2011,,LTD,Registered\n"
            "NOT-A-VALID-NZBN,9999999,BAD NZBN TEST LIMITED,15/07/2020,,LTD,Registered\n",
        )
        conn = duckdb.connect(":memory:")
        try:
            bronze_sql = read_sql("bronze", "companies_core_data")
            bronze_path = tmp_path / "bronze.parquet"
            materialize_bronze_table(conn, bronze_sql, bad_csv, bronze_path)

            output_path = tmp_path / "silver.parquet"
            rejects_path = tmp_path / "rejects.parquet"
            transform_sql = read_sql("silver", "company")
            good_count, reject_count = materialize_silver_company(
                conn,
                transform_sql,
                bronze_path,
                "202611",
                output_path,
                rejects_path,
            )
            reject_rows = conn.execute(
                "SELECT nzbn_raw, company_number, reject_reason FROM read_parquet($path, hive_partitioning = false)",
                {"path": str(rejects_path)},
            ).fetchall()
        finally:
            conn.close()

        assert good_count == 1
        assert reject_count == 1
        assert reject_rows == [("NOT-A-VALID-NZBN", "9999999", "invalid_nzbn_format")]

    def test_duplicate_nzbn_within_a_month_is_deduped(self, tmp_path: Path) -> None:
        """Two rows sharing an NZBN within the same month collapse to one."""
        dup_csv = tmp_path / "companies_core_data.csv"
        dup_csv.write_text(
            "NZBN,COMPANY_IDENTIFIER,ENTITY_NAME,REGISTRATION_DATE,REMOVAL_DATE,ENTITY_TYPE,ENTITY_STATUS\n"
            "9429031075473,3405451,PARROT ANALYTICS LIMITED,01/06/2011,,LTD,Registered\n"
            "9429031075473,3405451,PARROT ANALYTICS LIMITED,01/06/2011,,LTD,Registered\n",
        )
        conn = duckdb.connect(":memory:")
        try:
            bronze_sql = read_sql("bronze", "companies_core_data")
            bronze_path = tmp_path / "bronze.parquet"
            materialize_bronze_table(conn, bronze_sql, dup_csv, bronze_path)

            output_path = tmp_path / "silver.parquet"
            rejects_path = tmp_path / "rejects.parquet"
            transform_sql = read_sql("silver", "company")
            good_count, _reject_count = materialize_silver_company(
                conn,
                transform_sql,
                bronze_path,
                "202611",
                output_path,
                rejects_path,
            )
        finally:
            conn.close()
        assert good_count == 1
