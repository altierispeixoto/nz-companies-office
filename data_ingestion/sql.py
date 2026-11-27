"""Loads the medallion pipeline's DuckDB SQL transform files from data_ingestion/sql/."""

from __future__ import annotations

from nz_companies_office.config import SETTINGS

SQL_DIR = SETTINGS.project_root / "data_ingestion" / "sql"


def read_sql(*parts: str) -> str:
    """Read a .sql file's text, relative to the data_ingestion/sql/ directory.

    Args:
        *parts: Path segments under data_ingestion/sql/, e.g.
            ``read_sql("bronze", "companies_core_data")`` reads
            ``data_ingestion/sql/bronze/companies_core_data.sql``.

    Returns:
        The file's contents as a single SQL ``SELECT`` statement.

    """
    path = SQL_DIR.joinpath(*parts).with_suffix(".sql")
    return path.read_text()
