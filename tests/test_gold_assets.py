"""Tests for gold-layer medallion assets."""

from __future__ import annotations

from typing import TYPE_CHECKING

import duckdb

from nz_companies_office.orchestration.assets.gold import materialize_gold_company_dim
from nz_companies_office.orchestration.assets.gold import materialize_gold_company_status_changes
from nz_companies_office.orchestration.assets.gold import previous_partition_key
from nz_companies_office.orchestration.sql import read_sql

if TYPE_CHECKING:
    from pathlib import Path

_EXPECTED_DIM_ROW_COUNT = 2


def _write_silver_month(
    conn: duckdb.DuckDBPyConnection,
    silver_dir: Path,
    month: str,
    rows: list[tuple[str, str, str, str, str]],
) -> None:
    """Write a tiny silver_company-shaped Parquet partition for one month.

    Each row is (nzbn, company_number, entity_name, entity_type, entity_status).
    """
    partition_dir = silver_dir / "company" / f"snapshot_month={month}"
    partition_dir.mkdir(parents=True, exist_ok=True)
    values = ", ".join(
        f"('{nzbn}', '{company_number}', '{entity_name}', '{entity_type}', '{entity_status}', NULL, NULL, '{month}')"
        for nzbn, company_number, entity_name, entity_type, entity_status in rows
    )
    conn.execute(
        "COPY ("  # noqa: S608
        "SELECT * FROM (VALUES " + values + ") AS t(nzbn, company_number, entity_name, entity_type, entity_status, "
        "incorporation_date, removal_date, snapshot_month)"
        ") TO $path (FORMAT PARQUET)",
        {"path": str(partition_dir / "part-0.parquet")},
    )


class TestMaterializeGoldCompanyDim:
    """Tests for materialize_gold_company_dim using the real sql/gold/dims/company_dim.sql transform."""

    def test_latest_snapshot_month_wins(self, tmp_path: Path) -> None:
        """When a company appears in two months, the dim reflects the later month's status."""
        conn = duckdb.connect(":memory:")
        try:
            _write_silver_month(
                conn,
                tmp_path,
                "202610",
                [("9429031075473", "3405451", "PARROT ANALYTICS LIMITED", "LTD", "Registered")],
            )
            _write_silver_month(
                conn,
                tmp_path,
                "202611",
                [("9429031075473", "3405451", "PARROT ANALYTICS LIMITED", "LTD", "Removed")],
            )
            select_sql = read_sql("gold", "dims", "company_dim")
            silver_glob = str(tmp_path / "company" / "snapshot_month=*" / "part-0.parquet")
            output_path = tmp_path / "gold" / "company_dim" / "part-0.parquet"
            row_count = materialize_gold_company_dim(conn, select_sql, silver_glob, output_path)
            rows = conn.execute(
                "SELECT nzbn, entity_status, as_of_snapshot_month FROM read_parquet($p, hive_partitioning = false)",
                {"p": str(output_path)},
            ).fetchall()
        finally:
            conn.close()

        assert row_count == 1
        assert rows == [("9429031075473", "Removed", "202611")]

    def test_one_row_per_distinct_nzbn(self, tmp_path: Path) -> None:
        """Two different companies produce two dim rows, each from their own latest month."""
        conn = duckdb.connect(":memory:")
        try:
            _write_silver_month(
                conn,
                tmp_path,
                "202611",
                [
                    ("9429031075473", "3405451", "PARROT ANALYTICS LIMITED", "LTD", "Registered"),
                    ("9429031193450", "3301188", "PEAZY LIMITED", "LTD", "Removed"),
                ],
            )
            select_sql = read_sql("gold", "dims", "company_dim")
            silver_glob = str(tmp_path / "company" / "snapshot_month=*" / "part-0.parquet")
            output_path = tmp_path / "gold" / "company_dim" / "part-0.parquet"
            row_count = materialize_gold_company_dim(conn, select_sql, silver_glob, output_path)
        finally:
            conn.close()
        assert row_count == _EXPECTED_DIM_ROW_COUNT


class TestPreviousPartitionKey:
    """Tests for previous_partition_key."""

    def test_returns_prior_month_when_present(self) -> None:
        """The month immediately before the given one, by sort order, is returned."""
        assert previous_partition_key("202609", ["202607", "202608", "202609", "202610"]) == "202608"

    def test_returns_none_for_earliest_month(self) -> None:
        """The earliest month in the list has no predecessor."""
        assert previous_partition_key("202607", ["202607", "202608", "202609"]) is None

    def test_ignores_input_order(self) -> None:
        """Result is based on sorted order, independent of the input list's order."""
        assert previous_partition_key("202609", ["202610", "202607", "202609", "202608"]) == "202608"


class TestMaterializeGoldCompanyStatusChanges:
    """Tests for materialize_gold_company_status_changes using the real SCD2 fact SQL."""

    def test_status_flip_produces_one_change_row(self, tmp_path: Path) -> None:
        """A company whose status changes between two months produces exactly one fact row."""
        conn = duckdb.connect(":memory:")
        try:
            _write_silver_month(
                conn,
                tmp_path,
                "202610",
                [("9429031075473", "3405451", "PARROT ANALYTICS LIMITED", "LTD", "Registered")],
            )
            _write_silver_month(
                conn,
                tmp_path,
                "202611",
                [("9429031075473", "3405451", "PARROT ANALYTICS LIMITED", "LTD", "Removed")],
            )
            select_sql = read_sql("gold", "facts", "company_status_changes")
            current_path = tmp_path / "company" / "snapshot_month=202611" / "part-0.parquet"
            previous_path = tmp_path / "company" / "snapshot_month=202610" / "part-0.parquet"
            output_path = tmp_path / "gold" / "company_status_changes" / "part-0.parquet"
            row_count = materialize_gold_company_status_changes(
                conn,
                select_sql,
                current_path,
                previous_path,
                "202611",
                output_path,
            )
            rows = conn.execute(
                "SELECT nzbn, previous_status, new_status, previous_snapshot_month "
                "FROM read_parquet($p, hive_partitioning = false)",
                {"p": str(output_path)},
            ).fetchall()
        finally:
            conn.close()

        assert row_count == 1
        assert rows == [("9429031075473", "Registered", "Removed", "202610")]

    def test_unchanged_status_produces_no_rows(self, tmp_path: Path) -> None:
        """A company whose status is identical in both months produces zero fact rows."""
        conn = duckdb.connect(":memory:")
        try:
            _write_silver_month(
                conn,
                tmp_path,
                "202610",
                [("9429031075473", "3405451", "PARROT ANALYTICS LIMITED", "LTD", "Registered")],
            )
            _write_silver_month(
                conn,
                tmp_path,
                "202611",
                [("9429031075473", "3405451", "PARROT ANALYTICS LIMITED", "LTD", "Registered")],
            )
            select_sql = read_sql("gold", "facts", "company_status_changes")
            current_path = tmp_path / "company" / "snapshot_month=202611" / "part-0.parquet"
            previous_path = tmp_path / "company" / "snapshot_month=202610" / "part-0.parquet"
            output_path = tmp_path / "gold" / "company_status_changes" / "part-0.parquet"
            row_count = materialize_gold_company_status_changes(
                conn,
                select_sql,
                current_path,
                previous_path,
                "202611",
                output_path,
            )
        finally:
            conn.close()
        assert row_count == 0

    def test_no_previous_month_produces_no_rows_not_an_error(self, tmp_path: Path) -> None:
        """The earliest available partition (no prior month) yields zero rows, not an error."""
        conn = duckdb.connect(":memory:")
        try:
            _write_silver_month(
                conn,
                tmp_path,
                "202607",
                [("9429031075473", "3405451", "PARROT ANALYTICS LIMITED", "LTD", "Registered")],
            )
            select_sql = read_sql("gold", "facts", "company_status_changes")
            only_path = tmp_path / "company" / "snapshot_month=202607" / "part-0.parquet"
            output_path = tmp_path / "gold" / "company_status_changes" / "part-0.parquet"
            # No previous month exists: caller passes the same path for current and previous,
            # per materialize_gold_company_status_changes's documented edge-case behaviour.
            row_count = materialize_gold_company_status_changes(
                conn,
                select_sql,
                only_path,
                only_path,
                "202607",
                output_path,
            )
        finally:
            conn.close()
        assert row_count == 0
