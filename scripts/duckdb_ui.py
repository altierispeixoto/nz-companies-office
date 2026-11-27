"""Launch DuckDB's built-in web UI with views over the silver/gold medallion layers.

Registers one view per silver/gold table, pointed at its Parquet glob via the
same path-builder functions the Dagster assets use (so this can't drift from
where the pipeline actually writes), then starts DuckDB's `ui` extension —
a local browser UI with a SQL editor, catalog browser, and chart rendering.
"""

from __future__ import annotations

import logging
import time

import duckdb

from data_ingestion.assets.gold import gold_dim_output_path
from data_ingestion.assets.gold import gold_fact_output_path
from data_ingestion.assets.gold import silver_table_glob
from data_ingestion.catalog import GOLD_DIMS
from data_ingestion.catalog import GOLD_FACTS
from data_ingestion.catalog import SILVER_TABLES

logger = logging.getLogger(__name__)


def _create_view(conn: duckdb.DuckDBPyConnection, schema: str, name: str, glob_or_path: str) -> bool:
    """(Re)create a view over a Parquet glob/path, returning whether any data was found."""
    try:
        conn.execute(
            f"CREATE OR REPLACE VIEW {schema}.{name} AS "  # noqa: S608
            f"SELECT * FROM read_parquet('{glob_or_path}', hive_partitioning = false)"
        )
    except duckdb.IOException:
        logger.warning("skipped %s.%s: no materialized data at %s", schema, name, glob_or_path)
        return False
    logger.info("created view %s.%s", schema, name)
    return True


def build_catalog(conn: duckdb.DuckDBPyConnection) -> None:
    """Register `silver.*` and `gold.*` views over every materialized table."""
    conn.execute("CREATE SCHEMA IF NOT EXISTS silver")
    conn.execute("CREATE SCHEMA IF NOT EXISTS gold")

    created = 0
    for name in SILVER_TABLES:
        created += _create_view(conn, "silver", name, silver_table_glob(name))
    for name in GOLD_DIMS:
        created += _create_view(conn, "gold", name, str(gold_dim_output_path(name)))
    for name in GOLD_FACTS:
        created += _create_view(conn, "gold", name, str(gold_fact_output_path(name, "*")))

    total = len(SILVER_TABLES) + len(GOLD_DIMS) + len(GOLD_FACTS)
    logger.info("catalog ready: %d/%d views created", created, total)


def main() -> None:
    """Build the catalog and start DuckDB's web UI until interrupted."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    conn = duckdb.connect(":memory:")
    build_catalog(conn)

    conn.install_extension("ui")
    conn.load_extension("ui")
    conn.sql("CALL start_ui()")

    logger.info("DuckDB UI running at http://localhost:4213 — press Ctrl+C to stop")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("stopping")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
