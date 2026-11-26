"""Tests for the gold-to-Neo4j CSV export asset."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import duckdb

from nz_companies_office.orchestration.assets.gold import copy_passthrough_raw_files
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


class TestCopyPassthroughRawFiles:
    """Tests for copy_passthrough_raw_files."""

    def test_copies_existing_passthrough_files(self, tmp_path: Path) -> None:
        """A not-yet-migrated raw CSV present in the source month is copied into the export dir."""
        source_month = tmp_path / "202611"
        source_month.mkdir()
        (source_month / "companies_director.csv").write_text("NZBN,ENTITY_NAME\n9429031075473,TEST\n")
        export_dir = tmp_path / "export"
        copied = copy_passthrough_raw_files(source_month, export_dir)
        assert copied == ["companies_director.csv"]
        assert (export_dir / "companies_director.csv").read_text() == "NZBN,ENTITY_NAME\n9429031075473,TEST\n"

    def test_skips_missing_files_without_error(self, tmp_path: Path) -> None:
        """A passthrough file absent from the source month is simply skipped, not an error."""
        source_month = tmp_path / "202611"
        source_month.mkdir()
        export_dir = tmp_path / "export"
        copied = copy_passthrough_raw_files(source_month, export_dir)
        assert copied == []
        assert export_dir.exists()

    def test_does_not_copy_companies_core_data(self, tmp_path: Path) -> None:
        """companies_core_data.csv is sourced from gold, not copied through from raw."""
        source_month = tmp_path / "202611"
        source_month.mkdir()
        (source_month / "companies_core_data.csv").write_text("should not be copied")
        export_dir = tmp_path / "export"
        copy_passthrough_raw_files(source_month, export_dir)
        assert not (export_dir / "companies_core_data.csv").exists()
