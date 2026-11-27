"""Dagster resources shared across medallion pipeline assets."""

from __future__ import annotations

from dagster_duckdb import DuckDBResource

duckdb_resource = DuckDBResource(database=":memory:")
