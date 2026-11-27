"""Tests for the gold-to-Neo4j CSV export assets."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import duckdb

from data_ingestion.assets.gold import materialize_gold_export_csv
from data_ingestion.assets.gold import materialize_gold_export_csv_multi
from data_ingestion.sql import read_sql

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
    "ABN",
    "GST_NUMBER",
    "WEBSITE",
    "MAORI_BUSINESS_IDENTIFIER",
]


def _write_gold_company_dim(conn: duckdb.DuckDBPyConnection, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn.execute(
        "COPY ("
        "SELECT * FROM (VALUES ("
        "'9429031075473', '3405451', 'PARROT ANALYTICS LIMITED', "
        "DATE '2011-06-01', NULL::DATE, 'LTD', 'Registered', "
        "NULL::VARCHAR, NULL::VARCHAR, NULL::VARCHAR, NULL::VARCHAR, '202611'"
        ")) AS t(nzbn, company_number, entity_name, incorporation_date, removal_date, "
        "entity_type, entity_status, abn, gst_number, website, maori_business_identifier, "
        "as_of_snapshot_month)"
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


class TestMaterializeGoldExportCompanyAddress:
    """Tests for the two-input company_address export (sql/gold/export/company_address.sql)."""

    def test_joins_dim_and_address_dim(self, tmp_path: Path) -> None:
        """The export resolves address_key to its street/city/country via address_dim."""
        conn = duckdb.connect(":memory:")
        try:
            company_address_path = tmp_path / "company_address.parquet"
            address_dim_path = tmp_path / "address_dim.parquet"
            conn.execute(
                "COPY (SELECT * FROM (VALUES "
                "('9429031075473', 'REGISTERED_OFFICE', 'KEY1', DATE '2020-01-01', '202611')"
                ") AS t(nzbn, address_type, address_key, since, as_of_snapshot_month)) TO $path (FORMAT PARQUET)",
                {"path": str(company_address_path)},
            )
            conn.execute(
                "COPY (SELECT * FROM (VALUES "
                "('KEY1', 'Suite 1', 'Auckland', 'NZ', 'CBD', '1010', NULL, NULL)"
                ") AS t(address_key, street, city, country, suburb, postcode, care_of, paf_id)) "
                "TO $path (FORMAT PARQUET)",
                {"path": str(address_dim_path)},
            )
            select_sql = read_sql("gold", "export", "company_address")
            output_path = tmp_path / "companies_company_address.csv"
            row_count = materialize_gold_export_csv_multi(
                conn,
                select_sql,
                output_path,
                {"company_address_path": str(company_address_path), "address_dim_path": str(address_dim_path)},
            )
            rows = output_path.read_text().splitlines()
        finally:
            conn.close()
        assert row_count == 1
        assert rows[0].split(",") == [
            "NZBN",
            "ADDRESS_TYPE",
            "START_DATE",
            "STREET",
            "SUBURB",
            "CITY",
            "POSTCODE",
            "COUNTRY",
        ]
        assert rows[1].split(",") == [
            "9429031075473",
            "REGISTERED_OFFICE",
            "2020-01-01",
            "Suite 1",
            "CBD",
            "Auckland",
            "1010",
            "NZ",
        ]
