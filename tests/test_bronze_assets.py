"""Tests for bronze-layer medallion assets."""

from __future__ import annotations

from pathlib import Path

import duckdb

from data_ingestion.assets.bronze import materialize_bronze_table
from data_ingestion.sql import read_sql

_FIXTURE = "tests/fixtures/raw/companies_core_data.csv"
_FIXTURE_ROW_COUNT = 3


class TestMaterializeBronzeTable:
    """Tests for materialize_bronze_table using the real companies_core_data bronze SQL."""

    def test_row_count_matches_source(self, tmp_path: Path) -> None:
        """Bronze output has the same row count as the source CSV (minus header)."""
        output_path = tmp_path / "companies_core_data" / "snapshot_month=202611" / "part-0.parquet"
        select_sql = read_sql("bronze", "companies_core_data")
        conn = duckdb.connect(":memory:")
        try:
            row_count = materialize_bronze_table(conn, select_sql, Path(_FIXTURE), output_path)
        finally:
            conn.close()
        assert row_count == _FIXTURE_ROW_COUNT
        assert output_path.exists()

    def test_all_columns_are_varchar(self, tmp_path: Path) -> None:
        """Bronze preserves every column as a string, with no type coercion."""
        output_path = tmp_path / "companies_core_data" / "snapshot_month=202611" / "part-0.parquet"
        select_sql = read_sql("bronze", "companies_core_data")
        conn = duckdb.connect(":memory:")
        try:
            materialize_bronze_table(conn, select_sql, Path(_FIXTURE), output_path)
            types = conn.execute(
                "SELECT column_name, column_type "
                "FROM (DESCRIBE SELECT * FROM read_parquet($path, hive_partitioning = false))",
                {"path": str(output_path)},
            ).fetchall()
        finally:
            conn.close()
        assert types
        assert all(column_type == "VARCHAR" for _, column_type in types)

    def test_no_column_renaming_or_filtering(self, tmp_path: Path) -> None:
        """Bronze keeps the raw NZBN column names unchanged."""
        output_path = tmp_path / "companies_core_data" / "snapshot_month=202611" / "part-0.parquet"
        select_sql = read_sql("bronze", "companies_core_data")
        conn = duckdb.connect(":memory:")
        try:
            materialize_bronze_table(conn, select_sql, Path(_FIXTURE), output_path)
            columns = [
                row[0]
                for row in conn.execute(
                    "SELECT column_name FROM (DESCRIBE SELECT * FROM read_parquet($path, hive_partitioning = false))",
                    {"path": str(output_path)},
                ).fetchall()
            ]
        finally:
            conn.close()
        assert columns == [
            "NZBN",
            "COMPANY_IDENTIFIER",
            "ENTITY_NAME",
            "REGISTRATION_DATE",
            "REMOVAL_DATE",
            "ENTITY_TYPE",
            "ENTITY_STATUS",
        ]
