"""Tests for the gold-to-Neo4j CSV export asset."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import duckdb

from nz_companies_office.orchestration.assets.gold import materialize_gold_export_csv
from nz_companies_office.orchestration.sql import read_sql

if TYPE_CHECKING:
    from pathlib import Path

_EXPECTED_HEADER = [
    "NZBN",
    "COMPANY_IDENTIFIER",
    "ENTITY_NAME",
    "INCORPORATION_DATE",
    "REMOVAL_DATE",
    "ENTITY_TYPE",
    "ENTITY_STATUS",
]


def _write_gold_company_dim(conn: duckdb.DuckDBPyConnection, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn.execute(
        "COPY ("
        "SELECT * FROM (VALUES ("
        "'9429031075473', '3405451', 'PARROT ANALYTICS LIMITED', "
        "DATE '2011-06-01', NULL, 'LTD', 'Registered', '202611'"
        ")) AS t(nzbn, company_number, entity_name, incorporation_date, removal_date, "
        "entity_type, entity_status, as_of_snapshot_month)"
        ") TO $path (FORMAT PARQUET)",
        {"path": str(path)},
    )


class TestMaterializeGoldExportCsv:
    """Tests for materialize_gold_export_csv using the real companies_core_data export SQL."""

    def test_header_matches_cypher_expectations(self, tmp_path: Path) -> None:
        """The exported CSV header exactly matches what 01_companies.cypher expects."""
        conn = duckdb.connect(":memory:")
        try:
            dim_path = tmp_path / "company_dim.parquet"
            _write_gold_company_dim(conn, dim_path)
            select_sql = read_sql("gold", "export", "companies_core_data")
            output_path = tmp_path / "companies_core_data.csv"
            row_count = materialize_gold_export_csv(conn, select_sql, dim_path, output_path)
            header = output_path.read_text().splitlines()[0].split(",")
        finally:
            conn.close()
        assert row_count == 1
        assert header == _EXPECTED_HEADER

    def test_dates_are_written_as_iso(self, tmp_path: Path) -> None:
        """Dates are written in ISO format (yyyy-mm-dd), not NZBN's DD/MM/YYYY."""
        conn = duckdb.connect(":memory:")
        try:
            dim_path = tmp_path / "company_dim.parquet"
            _write_gold_company_dim(conn, dim_path)
            select_sql = read_sql("gold", "export", "companies_core_data")
            output_path = tmp_path / "companies_core_data.csv"
            materialize_gold_export_csv(conn, select_sql, dim_path, output_path)
            data_row = output_path.read_text().splitlines()[1].split(",")
        finally:
            conn.close()
        assert data_row[3] == datetime.date(2011, 6, 1).isoformat()
