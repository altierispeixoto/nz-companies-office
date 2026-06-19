"""Shared Neo4j query helpers for marimo walkthrough notebooks."""

from __future__ import annotations

import os

import marimo as mo
import polars as pl
from neo4j import GraphDatabase

URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
USER = os.environ.get("NEO4J_USER", "neo4j")
PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")

_driver: GraphDatabase.driver | None = None


def get_driver() -> GraphDatabase.driver:
    global _driver  # noqa: PLW0603
    if _driver is None:
        _driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    return _driver


def run_query(q: str) -> pl.DataFrame:
    with get_driver().session() as s:
        result = s.run(q)
        records = result.data()
    if not records:
        return pl.DataFrame()
    return pl.DataFrame(records)


def mo_table(q: str, **kwargs: object) -> mo.ui.table | mo.Html:
    df = run_query(q)
    if len(df) == 0:
        return mo.md("*No results*")
    return mo.ui.table(df, **kwargs)
