"""Tests for snapshot-month partition discovery."""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

import pytest

from nz_companies_office.orchestration.partitions import discover_snapshot_months

if TYPE_CHECKING:
    from pathlib import Path


def test_discover_snapshot_months_sorts_numeric_dirs(tmp_path: Path) -> None:
    """Numeric-named directories are returned, sorted ascending."""
    (tmp_path / "202608").mkdir()
    (tmp_path / "202607").mkdir()
    (tmp_path / "202609").mkdir()
    assert discover_snapshot_months(tmp_path) == ["202607", "202608", "202609"]


def test_discover_snapshot_months_skips_non_numeric_dirs(tmp_path: Path) -> None:
    """Non-numeric directory names are excluded."""
    (tmp_path / "202607").mkdir()
    (tmp_path / "lds-nz-addresses-SHP").mkdir()
    assert discover_snapshot_months(tmp_path) == ["202607"]


def test_discover_snapshot_months_skips_files(tmp_path: Path) -> None:
    """Regular files (e.g. .gitignore) are excluded, only directories count."""
    (tmp_path / "202607").mkdir()
    (tmp_path / ".gitignore").write_text("")
    assert discover_snapshot_months(tmp_path) == ["202607"]


def test_discover_snapshot_months_missing_root_returns_empty(tmp_path: Path) -> None:
    """A non-existent raw data directory yields no partitions, not an error."""
    assert discover_snapshot_months(tmp_path / "does-not-exist") == []


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits only")
def test_discover_snapshot_months_skips_unreadable_dirs(tmp_path: Path) -> None:
    """An unreadable directory (e.g. orphaned Docker-container-owned 202606) is skipped."""
    (tmp_path / "202607").mkdir()
    locked = tmp_path / "202606"
    locked.mkdir()
    locked.chmod(0o000)
    try:
        if os.access(locked, os.R_OK | os.X_OK):
            pytest.skip("running as a user that bypasses directory permission bits (e.g. root)")
        assert discover_snapshot_months(tmp_path) == ["202607"]
    finally:
        locked.chmod(0o700)
