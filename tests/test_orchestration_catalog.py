"""Tests for the silver/gold table registry."""

from __future__ import annotations

from nz_companies_office.orchestration.catalog import GOLD_DIMS
from nz_companies_office.orchestration.catalog import GOLD_FACTS
from nz_companies_office.orchestration.catalog import SILVER_TABLES


def test_silver_tables_non_empty_and_unique() -> None:
    """SILVER_TABLES lists at least one table and has no duplicate names."""
    assert SILVER_TABLES
    assert len(SILVER_TABLES) == len(set(SILVER_TABLES))


def test_gold_dims_non_empty_and_unique() -> None:
    """GOLD_DIMS lists at least one table and has no duplicate names."""
    assert GOLD_DIMS
    assert len(GOLD_DIMS) == len(set(GOLD_DIMS))


def test_gold_facts_non_empty_and_unique() -> None:
    """GOLD_FACTS lists at least one table and has no duplicate names."""
    assert GOLD_FACTS
    assert len(GOLD_FACTS) == len(set(GOLD_FACTS))


def test_gold_dims_and_facts_are_disjoint() -> None:
    """A table name cannot be registered as both a gold dimension and a gold fact."""
    assert not set(GOLD_DIMS) & set(GOLD_FACTS)
