"""Tests for the Increment 2 silver-layer transforms (shareholder, director, address, etc.)."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import duckdb

from data_ingestion.assets.bronze import materialize_bronze_table
from data_ingestion.assets.silver import materialize_silver_company_address
from data_ingestion.assets.silver import materialize_silver_table
from data_ingestion.sql import read_sql

if TYPE_CHECKING:
    from pathlib import Path

_MONTH = "202611"
_SHAREHOLDER_CSV = (
    "NZBN,ENTITY_NAME,SH_NAME,SH_TYPE,START_DATE,SH_STATUS,PARCEL_IDENTIFIER,ASSIGNMENT_IDENTIFIER,"
    "NUMBER_OF_SHARES,SH_EXTENSIVE_SHAREHOLDING_YN,SH_ADDRESS_PAF_ID,SH_ADDRESS_CARE_OF,SH_ADDRESS_1,"
    "SH_ADDRESS_2,SH_ADDRESS_3,SH_ADDRESS_4,SH_ADDRESS_POSTCODE,SH_ADDRESS_COUNTRY\n"
    "9429000001311,FOLEY WINES LIMITED,ALFA LEA HORTICULTURE LIMITED,Shareholder Company,29/09/2008,active,"
    "176898,1821514,903330,Y,,,300 Vickerman St,Lower Wairau,Blenheim,,,\n"
    "9429000001311,FOLEY WINES LIMITED,Wared  SEGER,Shareholder Individual,16/11/2020,active,"
    "4419770,4574011,882820,Y,,,,,,,,NEW ZEALAND\n"
)
_ALFA_LEA_SHARES = 903330
_EXPECTED_ADDRESS_ROW_COUNT = 3
_DIRECTOR_CSV = (
    "NZBN,ENTITY_NAME,START_DATE,FIRST_NAME,MIDDLE_NAMES,LAST_NAME,ASIC_DIR_YN,ACN,ASIC_COMPANY_NAME\n"
    "9429052039652,RANDHAWA NEW ZEALAND LIMITED,18/04/2024,Lovepreet,,SINGH,,,\n"
    "9429042162377,HOWIE FARMING LIMITED,28/01/2016,Daniel,Allan,HOWIE,,,\n"
)


def _bronze_from_csv(conn: duckdb.DuckDBPyConnection, tmp_path: Path, csv_text: str, name: str) -> Path:
    csv_path = tmp_path / f"{name}.csv"
    csv_path.write_text(csv_text)
    bronze_sql = read_sql("bronze", "companies_core_data")  # generic ALL_VARCHAR passthrough, works for any CSV
    bronze_path = tmp_path / f"{name}_bronze.parquet"
    materialize_bronze_table(conn, bronze_sql, csv_path, bronze_path)
    return bronze_path


class TestSilverShareholder:
    """Tests for sql/silver/shareholder.sql."""

    def test_typed_and_normalized(self, tmp_path: Path) -> None:
        """Share counts are typed, dates parsed, and name_key derived like the Cypher does today."""
        conn = duckdb.connect(":memory:")
        try:
            bronze_path = _bronze_from_csv(conn, tmp_path, _SHAREHOLDER_CSV, "shareholder")
            output_path = tmp_path / "silver.parquet"
            transform_sql = read_sql("silver", "shareholder")
            materialize_silver_table(
                conn,
                transform_sql,
                output_path,
                {"input_path": str(bronze_path), "month": _MONTH},
            )
            rows = conn.execute(
                "SELECT shareholder_name, number_of_shares, start_date, is_person, name_key "
                "FROM read_parquet($p, hive_partitioning = false) ORDER BY shareholder_name",
                {"p": str(output_path)},
            ).fetchall()
        finally:
            conn.close()
        assert rows[0][0] == "ALFA LEA HORTICULTURE LIMITED"
        assert rows[0][1] == _ALFA_LEA_SHARES
        assert rows[0][2] == datetime.date(2008, 9, 29)
        assert rows[0][3] is False
        # "Wared  SEGER" (double space) normalizes to "Wared SEGER" -> name_key "WAREDSEGER", is_person True
        assert rows[1][3] is True
        assert rows[1][4] == "WAREDSEGER"


class TestSilverDirector:
    """Tests for sql/silver/director.sql."""

    def test_full_name_and_dates(self, tmp_path: Path) -> None:
        """First/middle/last names concatenate into director_name, dates parse."""
        conn = duckdb.connect(":memory:")
        try:
            bronze_path = _bronze_from_csv(conn, tmp_path, _DIRECTOR_CSV, "director")
            output_path = tmp_path / "silver.parquet"
            transform_sql = read_sql("silver", "director")
            materialize_silver_table(
                conn,
                transform_sql,
                output_path,
                {"input_path": str(bronze_path), "month": _MONTH},
            )
            rows = conn.execute(
                "SELECT director_name, start_date FROM read_parquet($p, hive_partitioning = false) "
                "ORDER BY director_name",
                {"p": str(output_path)},
            ).fetchall()
        finally:
            conn.close()
        assert rows[0] == ("Daniel Allan HOWIE", datetime.date(2016, 1, 28))
        assert rows[1] == ("Lovepreet SINGH", datetime.date(2024, 4, 18))


class TestSilverCompanyAddress:
    """Tests for sql/silver/company_address.sql, unioning the three address sources."""

    def test_unions_all_three_sources(self, tmp_path: Path) -> None:
        """One row per (nzbn, address_type) comes out, regardless of which source it came from."""
        conn = duckdb.connect(":memory:")
        try:
            reg_office_csv = (
                "NZBN,ENTITY_NAME,START_DATE,REGISTERED_OFFICE_ADDRESS_PAF_ID,"
                "REGISTERED_OFFICE_ADDRESS_CARE_OF,REGISTERED_OFFICE_ADDRESS_1,REGISTERED_OFFICE_ADDRESS_2,"
                "REGISTERED_OFFICE_ADDRESS_3,REGISTERED_OFFICE_ADDRESS_4,REGISTERED_OFFICE_ADDRESS_POSTCODE,"
                "REGISTERED_OFFICE_ADDRESS_COUNTRY\n"
                "9429031075473,PARROT ANALYTICS LIMITED,13/11/2023,,Directors,Suite 1,20 Augustus Terrace,"
                "Auckland,,1052,NEW ZEALAND\n"
            )
            service_csv = (
                "NZBN,ENTITY_NAME,START_DATE,ADDRESS_FOR_SERVICE_PAF_ID,ADDRESS_FOR_SERVICE_CARE_OF,"
                "ADDRESS_FOR_SERVICE_1,ADDRESS_FOR_SERVICE_2,ADDRESS_FOR_SERVICE_3,ADDRESS_FOR_SERVICE_4,"
                "ADDRESS_FOR_SERVICE_POSTCODE,ADDRESS_FOR_SERVICE_COUNTRY\n"
                "9429031075473,PARROT ANALYTICS LIMITED,20/11/2023,,Directors,Suite 1,20 Augustus Terrace,"
                "Auckland,,1052,NEW ZEALAND\n"
            )
            public_csv = (
                "NZBN,ENTITY_NAME,TYPE,START_DATE,ADDRESS_PAF_ID,ADDRESS_CARE_OF,ADDRESS_1,ADDRESS_2,"
                "ADDRESS_3,ADDRESS_4,ADDRESS_POSTCODE,ADDRESS_COUNTRY\n"
                "9429031075473,PARROT ANALYTICS LIMITED,Other,01/01/2020,,,123 Queen St,,Auckland,,1010,"
                "NEW ZEALAND\n"
            )
            reg_office_path = _bronze_from_csv(conn, tmp_path, reg_office_csv, "reg_office")
            service_path = _bronze_from_csv(conn, tmp_path, service_csv, "service")
            public_path = _bronze_from_csv(conn, tmp_path, public_csv, "public")
            output_path = tmp_path / "silver.parquet"
            transform_sql = read_sql("silver", "company_address")
            row_count = materialize_silver_company_address(
                conn,
                transform_sql,
                reg_office_path,
                service_path,
                public_path,
                _MONTH,
                output_path,
            )
            rows = conn.execute(
                "SELECT address_type, street, city FROM read_parquet($p, hive_partitioning = false) "
                "ORDER BY address_type",
                {"p": str(output_path)},
            ).fetchall()
        finally:
            conn.close()
        assert row_count == _EXPECTED_ADDRESS_ROW_COUNT
        assert rows == [
            ("PUBLIC", "123 Queen St", "Auckland"),
            ("REGISTERED_OFFICE", "Suite 1", "Auckland"),
            ("SERVICE", "Suite 1", "Auckland"),
        ]

    def test_public_type_mapping_overrides_default(self, tmp_path: Path) -> None:
        """A public-address row typed 'Registered Office' is mapped to REGISTERED_OFFICE, not PUBLIC."""
        conn = duckdb.connect(":memory:")
        try:
            empty_header = (
                "NZBN,ENTITY_NAME,START_DATE,REGISTERED_OFFICE_ADDRESS_PAF_ID,"
                "REGISTERED_OFFICE_ADDRESS_CARE_OF,REGISTERED_OFFICE_ADDRESS_1,REGISTERED_OFFICE_ADDRESS_2,"
                "REGISTERED_OFFICE_ADDRESS_3,REGISTERED_OFFICE_ADDRESS_4,REGISTERED_OFFICE_ADDRESS_POSTCODE,"
                "REGISTERED_OFFICE_ADDRESS_COUNTRY\n"
            )
            empty_service_header = (
                "NZBN,ENTITY_NAME,START_DATE,ADDRESS_FOR_SERVICE_PAF_ID,ADDRESS_FOR_SERVICE_CARE_OF,"
                "ADDRESS_FOR_SERVICE_1,ADDRESS_FOR_SERVICE_2,ADDRESS_FOR_SERVICE_3,ADDRESS_FOR_SERVICE_4,"
                "ADDRESS_FOR_SERVICE_POSTCODE,ADDRESS_FOR_SERVICE_COUNTRY\n"
            )
            public_csv = (
                "NZBN,ENTITY_NAME,TYPE,START_DATE,ADDRESS_PAF_ID,ADDRESS_CARE_OF,ADDRESS_1,ADDRESS_2,"
                "ADDRESS_3,ADDRESS_4,ADDRESS_POSTCODE,ADDRESS_COUNTRY\n"
                "9429031075473,PARROT ANALYTICS LIMITED,Registered Office,01/01/2020,,,123 Queen St,,"
                "Auckland,,1010,NEW ZEALAND\n"
            )
            reg_office_path = _bronze_from_csv(conn, tmp_path, empty_header, "reg_office")
            service_path = _bronze_from_csv(conn, tmp_path, empty_service_header, "service")
            public_path = _bronze_from_csv(conn, tmp_path, public_csv, "public")
            output_path = tmp_path / "silver.parquet"
            transform_sql = read_sql("silver", "company_address")
            materialize_silver_company_address(
                conn,
                transform_sql,
                reg_office_path,
                service_path,
                public_path,
                _MONTH,
                output_path,
            )
            rows = conn.execute(
                "SELECT address_type FROM read_parquet($p, hive_partitioning = false)",
                {"p": str(output_path)},
            ).fetchall()
        finally:
            conn.close()
        assert rows == [("REGISTERED_OFFICE",)]


class TestSilverCompanyIndustry:
    """Tests for sql/silver/company_industry.sql."""

    def test_filters_malformed_industry_codes(self, tmp_path: Path) -> None:
        """A code that doesn't match the ANZSIC pattern (letter + 6 digits) is dropped."""
        csv_text = (
            "NZBN,ENTITY_NAME,START_DATE,INDUSTRY_CLASSIFICATION_CODE,INDUSTRY_CLASSIFICATION_DESCRIPTION\n"
            "9429031075473,PARROT ANALYTICS LIMITED,01/01/2020,A011100,Sheep Farming\n"
            "9429031075473,PARROT ANALYTICS LIMITED,01/01/2020,BADCODE,Not Real\n"
        )
        conn = duckdb.connect(":memory:")
        try:
            bronze_path = _bronze_from_csv(conn, tmp_path, csv_text, "industry")
            output_path = tmp_path / "silver.parquet"
            transform_sql = read_sql("silver", "company_industry")
            row_count = materialize_silver_table(
                conn,
                transform_sql,
                output_path,
                {"input_path": str(bronze_path), "month": _MONTH},
            )
        finally:
            conn.close()
        assert row_count == 1


class TestSilverInsolvency:
    """Tests for sql/silver/insolvency.sql."""

    def test_appointee_name_concatenates_and_dates_parse(self, tmp_path: Path) -> None:
        """Appointee names concatenate (double space when middle is blank, matching Cypher today)."""
        csv_text = (
            "NZBN,ENTITY_NAME,START_DATE,INSOLVENCY_TYPE,APPOINTMENT_TYPE,APPOINTEE_FIRST_NAME,"
            "APPOINTEE_MIDDLE_NAMES,APPOINTEE_LAST_NAME,APPOINTMENT_DATE,APPOINTMENT_VACATED_DATE,"
            "ORGANISATION,RESSOLUTION_OF_SOLVENCY\n"
            "9429031075473,PARROT ANALYTICS LIMITED,,Liquidation,Liquidator,John,,SMITH,"
            "01/02/2021,15/06/2022,ABC Insolvency Ltd,\n"
        )
        conn = duckdb.connect(":memory:")
        try:
            bronze_path = _bronze_from_csv(conn, tmp_path, csv_text, "insolvency")
            output_path = tmp_path / "silver.parquet"
            transform_sql = read_sql("silver", "insolvency")
            materialize_silver_table(
                conn,
                transform_sql,
                output_path,
                {"input_path": str(bronze_path), "month": _MONTH},
            )
            rows = conn.execute(
                "SELECT appointee, appointment_date, appointment_vacated_date "
                "FROM read_parquet($p, hive_partitioning = false)",
                {"p": str(output_path)},
            ).fetchall()
        finally:
            conn.close()
        assert rows == [("John  SMITH", datetime.date(2021, 2, 1), datetime.date(2022, 6, 15))]


class TestSilverSimpleLookups:
    """Tests for the simple one-column-per-company silver tables (abn/gst/website/maori)."""

    def test_company_abn(self, tmp_path: Path) -> None:
        """ABN passes through, blank values become NULL not empty string."""
        csv_text = "NZBN,ENTITY_NAME,ABN\n9429031075473,PARROT ANALYTICS LIMITED,51824753556\n"
        conn = duckdb.connect(":memory:")
        try:
            bronze_path = _bronze_from_csv(conn, tmp_path, csv_text, "abn")
            output_path = tmp_path / "silver.parquet"
            transform_sql = read_sql("silver", "company_abn")
            materialize_silver_table(
                conn,
                transform_sql,
                output_path,
                {"input_path": str(bronze_path), "month": _MONTH},
            )
            rows = conn.execute(
                "SELECT nzbn, abn FROM read_parquet($p, hive_partitioning = false)",
                {"p": str(output_path)},
            ).fetchall()
        finally:
            conn.close()
        assert rows == [("9429031075473", "51824753556")]

    def test_maori_business_identifier(self, tmp_path: Path) -> None:
        """IDENTIFYING_FACTOR renames to maori_business_identifier."""
        csv_text = (
            "NZBN,ENTITY_NAME,ENTITY_TYPE,START_DATE,IDENTIFYING_FACTOR\n"
            "9429031075473,PARROT ANALYTICS LIMITED,LTD,01/01/2020,Maori Business\n"
        )
        conn = duckdb.connect(":memory:")
        try:
            bronze_path = _bronze_from_csv(conn, tmp_path, csv_text, "maori")
            output_path = tmp_path / "silver.parquet"
            transform_sql = read_sql("silver", "maori_business_identifier")
            materialize_silver_table(
                conn,
                transform_sql,
                output_path,
                {"input_path": str(bronze_path), "month": _MONTH},
            )
            rows = conn.execute(
                "SELECT maori_business_identifier FROM read_parquet($p, hive_partitioning = false)",
                {"p": str(output_path)},
            ).fetchall()
        finally:
            conn.close()
        assert rows == [("Maori Business",)]
