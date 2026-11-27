"""Tests for medallion pipeline asset checks."""

from __future__ import annotations

from typing import TYPE_CHECKING

import duckdb

from data_ingestion.assets.gold import count_duplicate_nzbn
from data_ingestion.assets.silver import REJECT_RATE_THRESHOLD
from data_ingestion.assets.silver import compute_reject_rate

if TYPE_CHECKING:
    from pathlib import Path

_GOOD_ROW_COUNT = 999
_BAD_ROW_COUNT_UNDER_THRESHOLD = 1
_BAD_ROW_COUNT_OVER_THRESHOLD = 50


def _write_rows(conn: duckdb.DuckDBPyConnection, path: Path, count: int, column: str = "x") -> None:
    """Write a Parquet file with `count` rows of a single dummy column."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn.execute(
        f"COPY (SELECT range AS {column} FROM range({count})) TO $path (FORMAT PARQUET)",  # noqa: S608
        {"path": str(path)},
    )


class TestComputeRejectRate:
    """Tests for compute_reject_rate."""

    def test_rate_under_threshold_passes(self, tmp_path: Path) -> None:
        """1 reject out of 1000 rows (0.1%) is at the threshold, not over it."""
        conn = duckdb.connect(":memory:")
        try:
            good_path = tmp_path / "good.parquet"
            rejects_path = tmp_path / "rejects.parquet"
            _write_rows(conn, good_path, _GOOD_ROW_COUNT)
            _write_rows(conn, rejects_path, _BAD_ROW_COUNT_UNDER_THRESHOLD)
            rate = compute_reject_rate(conn, good_path, rejects_path)
        finally:
            conn.close()
        assert rate <= REJECT_RATE_THRESHOLD

    def test_rate_over_threshold_fails(self, tmp_path: Path) -> None:
        """50 rejects out of ~1000 rows (~5%) is well over the 0.1% threshold."""
        conn = duckdb.connect(":memory:")
        try:
            good_path = tmp_path / "good.parquet"
            rejects_path = tmp_path / "rejects.parquet"
            _write_rows(conn, good_path, _GOOD_ROW_COUNT)
            _write_rows(conn, rejects_path, _BAD_ROW_COUNT_OVER_THRESHOLD)
            rate = compute_reject_rate(conn, good_path, rejects_path)
        finally:
            conn.close()
        assert rate > REJECT_RATE_THRESHOLD

    def test_no_rows_at_all_is_zero_rate(self, tmp_path: Path) -> None:
        """An empty month (no good rows, no rejects) is not treated as a 100% reject rate."""
        conn = duckdb.connect(":memory:")
        try:
            good_path = tmp_path / "good.parquet"
            rejects_path = tmp_path / "rejects.parquet"
            _write_rows(conn, good_path, 0)
            _write_rows(conn, rejects_path, 0)
            rate = compute_reject_rate(conn, good_path, rejects_path)
        finally:
            conn.close()
        assert rate == 0.0


class TestCountDuplicateNzbn:
    """Tests for count_duplicate_nzbn."""

    def test_no_duplicates(self, tmp_path: Path) -> None:
        """A dim with one row per nzbn has zero duplicates."""
        conn = duckdb.connect(":memory:")
        try:
            path = tmp_path / "dim.parquet"
            conn.execute(
                "COPY (SELECT * FROM (VALUES ('A'), ('B'), ('C')) AS t(nzbn)) TO $path (FORMAT PARQUET)",
                {"path": str(path)},
            )
            duplicate_count = count_duplicate_nzbn(conn, path)
        finally:
            conn.close()
        assert duplicate_count == 0

    def test_detects_duplicate_nzbn(self, tmp_path: Path) -> None:
        """A dim with the same nzbn twice is flagged."""
        conn = duckdb.connect(":memory:")
        try:
            path = tmp_path / "dim.parquet"
            conn.execute(
                "COPY (SELECT * FROM (VALUES ('A'), ('A'), ('B')) AS t(nzbn)) TO $path (FORMAT PARQUET)",
                {"path": str(path)},
            )
            duplicate_count = count_duplicate_nzbn(conn, path)
        finally:
            conn.close()
        assert duplicate_count == 1
