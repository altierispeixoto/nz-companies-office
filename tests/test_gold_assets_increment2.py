"""Tests for the Increment 2 gold dims/facts (shareholding, director, address)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import duckdb

from data_ingestion.assets.gold import materialize_gold_table
from data_ingestion.sql import read_sql

if TYPE_CHECKING:
    from pathlib import Path

_MONTH = "202611"


def _write_silver_shareholder_month(
    conn: duckdb.DuckDBPyConnection,
    silver_dir: Path,
    month: str,
    rows: list[tuple[str, str, int]],
) -> None:
    """Write a tiny silver_shareholder-shaped Parquet partition. Rows: (nzbn, name, shares)."""
    partition_dir = silver_dir / "shareholder" / f"snapshot_month={month}"
    partition_dir.mkdir(parents=True, exist_ok=True)
    values = ", ".join(
        f"('{nzbn}', '{name}', {shares}, 'Shareholder Company', false, '{name}', false, 'active', '{month}')"
        for nzbn, name, shares in rows
    )
    conn.execute(
        "COPY (SELECT * FROM (VALUES "  # noqa: S608
        + values
        + ") AS t(nzbn, shareholder_name, number_of_shares, sh_type, is_person, name_key, "
        "extensive_shareholding, sh_status, snapshot_month)"
        ") TO $path (FORMAT PARQUET)",
        {"path": str(partition_dir / "part-0.parquet")},
    )


class TestGoldShareholding:
    """Tests for sql/gold/dims/shareholding.sql."""

    def test_share_percentage_and_majority(self, tmp_path: Path) -> None:
        """Two shareholders of one company get percentages summing to 100; the bigger is majority."""
        conn = duckdb.connect(":memory:")
        try:
            _write_silver_shareholder_month(
                conn,
                tmp_path,
                _MONTH,
                [("9429031075473", "ALICE", 750), ("9429031075473", "BOB", 250)],
            )
            select_sql = read_sql("gold", "dims", "shareholding")
            silver_glob = str(tmp_path / "shareholder" / "snapshot_month=*" / "part-0.parquet")
            output_path = tmp_path / "gold" / "shareholding" / "part-0.parquet"
            materialize_gold_table(conn, select_sql, output_path, {"silver_glob": silver_glob})
            rows = conn.execute(
                "SELECT shareholder_name, share_percentage, is_majority "
                "FROM read_parquet($p, hive_partitioning = false) ORDER BY shareholder_name",
                {"p": str(output_path)},
            ).fetchall()
        finally:
            conn.close()
        assert rows == [("ALICE", 75.0, True), ("BOB", 25.0, False)]

    def test_multiple_parcels_summed(self, tmp_path: Path) -> None:
        """Two parcel rows for the same shareholder+company in one month sum, not overwrite."""
        conn = duckdb.connect(":memory:")
        try:
            _write_silver_shareholder_month(
                conn,
                tmp_path,
                _MONTH,
                [("9429031075473", "ALICE", 300), ("9429031075473", "ALICE", 200)],
            )
            select_sql = read_sql("gold", "dims", "shareholding")
            silver_glob = str(tmp_path / "shareholder" / "snapshot_month=*" / "part-0.parquet")
            output_path = tmp_path / "gold" / "shareholding" / "part-0.parquet"
            materialize_gold_table(conn, select_sql, output_path, {"silver_glob": silver_glob})
            rows = conn.execute(
                "SELECT shares FROM read_parquet($p, hive_partitioning = false)",
                {"p": str(output_path)},
            ).fetchall()
        finally:
            conn.close()
        assert rows == [(500,)]


class TestGoldShareholdingChanges:
    """Tests for sql/gold/facts/shareholding_changes.sql."""

    def test_new_increased_exited(self, tmp_path: Path) -> None:
        """A new shareholder, an increase, and an exit are each classified correctly."""
        conn = duckdb.connect(":memory:")
        try:
            _write_silver_shareholder_month(
                conn,
                tmp_path,
                "202610",
                [("NZBN1", "ALICE", 100), ("NZBN1", "BOB", 50)],
            )
            _write_silver_shareholder_month(
                conn,
                tmp_path,
                "202611",
                [("NZBN1", "ALICE", 200), ("NZBN1", "CAROL", 10)],
            )
            select_sql = read_sql("gold", "facts", "shareholding_changes")
            current_path = tmp_path / "shareholder" / "snapshot_month=202611" / "part-0.parquet"
            previous_path = tmp_path / "shareholder" / "snapshot_month=202610" / "part-0.parquet"
            output_path = tmp_path / "gold" / "shareholding_changes" / "part-0.parquet"
            materialize_gold_table(
                conn,
                select_sql,
                output_path,
                {"current_path": str(current_path), "previous_path": str(previous_path), "month": "202611"},
            )
            rows = conn.execute(
                "SELECT shareholder_name, change_type FROM read_parquet($p, hive_partitioning = false) "
                "ORDER BY shareholder_name",
                {"p": str(output_path)},
            ).fetchall()
        finally:
            conn.close()
        assert rows == [("ALICE", "INCREASED"), ("BOB", "EXITED"), ("CAROL", "NEW")]


class TestGoldAddressDim:
    """Tests for sql/gold/dims/address_dim.sql deduping across address types."""

    def test_same_street_city_country_dedupes_to_one_address(self, tmp_path: Path) -> None:
        """Two rows with identical street/city/country collapse to a single address_key."""
        partition_dir = tmp_path / "company_address" / f"snapshot_month={_MONTH}"
        partition_dir.mkdir(parents=True)
        conn = duckdb.connect(":memory:")
        try:
            conn.execute(
                "COPY (SELECT * FROM (VALUES "
                "('NZBN1', 'REGISTERED_OFFICE', NULL, NULL, NULL, 'Suite 1', 'CBD', 'Auckland', '1010', 'NZ'), "
                "('NZBN1', 'SERVICE', NULL, NULL, NULL, 'Suite 1', 'CBD', 'Auckland', '1010', 'NZ')"
                ") AS t(nzbn, address_type, start_date, care_of, paf_id, street, suburb, city, postcode, "
                "country)"
                ") TO $path (FORMAT PARQUET)",
                {"path": str(partition_dir / "part-0.parquet")},
            )
            select_sql = read_sql("gold", "dims", "address_dim")
            silver_glob = str(tmp_path / "company_address" / "snapshot_month=*" / "part-0.parquet")
            output_path = tmp_path / "gold" / "address_dim" / "part-0.parquet"
            row_count = materialize_gold_table(conn, select_sql, output_path, {"silver_glob": silver_glob})
        finally:
            conn.close()
        assert row_count == 1
