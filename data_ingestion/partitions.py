"""Snapshot-month partitioning for the medallion pipeline.

Raw NZBN exports are fixed historical snapshots dropped manually into
``data/raw/<yyyymm>/``, not a guaranteed rolling calendar window, so
partitions are discovered from disk rather than generated from a date range.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from dagster import StaticPartitionsDefinition

from nz_companies_office.config import SETTINGS

if TYPE_CHECKING:
    from pathlib import Path


def discover_snapshot_months(raw_data_dir: Path) -> list[str]:
    """Find valid snapshot-month partitions under a raw data directory.

    A valid partition is a numeric-named, readable subdirectory (e.g.
    ``202611``). Non-numeric names and unreadable directories — such as the
    orphaned, container-owned ``data/raw/202606`` left behind by a stale
    Docker bind mount — are skipped rather than raised as errors.

    Args:
        raw_data_dir: Directory containing one subdirectory per snapshot month.

    Returns:
        Sorted list of snapshot-month strings (e.g. ``["202607", "202608"]``).

    """
    if not raw_data_dir.is_dir():
        return []
    return sorted(
        entry.name
        for entry in raw_data_dir.iterdir()
        if entry.is_dir() and entry.name.isdigit() and os.access(entry, os.R_OK | os.X_OK)
    )


snapshot_month_partitions = StaticPartitionsDefinition(discover_snapshot_months(SETTINGS.raw_data_dir))
