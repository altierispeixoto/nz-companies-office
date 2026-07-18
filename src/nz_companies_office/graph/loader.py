"""Load and reset the Neo4j company-register graph."""

from __future__ import annotations

import logging
import subprocess
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from nz_companies_office.config import SETTINGS
from nz_companies_office.db.connection import get_driver
from nz_companies_office.db.repository import Neo4jRepository
from nz_companies_office.exceptions import Neo4jConnectionError

logger = logging.getLogger(__name__)

INDEXES = [
    "CREATE INDEX company_nzbn IF NOT EXISTS FOR (c:Company) ON (c.nzbn)",
    "CREATE INDEX company_number_idx IF NOT EXISTS FOR (c:Company) ON (c.company_number)",
    "CREATE INDEX director_name_idx IF NOT EXISTS FOR (d:Director) ON (d.name)",
    "CREATE INDEX shareholder_name_idx IF NOT EXISTS FOR (s:Shareholder) ON (s.name)",
    "CREATE INDEX address_physical_idx IF NOT EXISTS FOR (a:Address) ON (a.street, a.city, a.country)",
    "CREATE INDEX industry_code_idx IF NOT EXISTS FOR (ind:Industry) ON (ind.code)",
    "CREATE INDEX trading_name_idx IF NOT EXISTS FOR (t:TradingName) ON (t.name)",
    "CREATE INDEX insolvency_idx IF NOT EXISTS FOR (i:Insolvency) ON (i.type, i.appointment_type, i.appointee)",
    "CREATE INDEX trading_area_idx IF NOT EXISTS FOR (ta:TradingArea) ON (ta.name)",
    "CREATE INDEX company_name_idx IF NOT EXISTS FOR (c:Company) ON (c.name)",
    "CREATE INDEX shareholder_surname_idx IF NOT EXISTS FOR (s:Shareholder) ON (s.surname)",
    "CREATE INDEX director_last_name_idx IF NOT EXISTS FOR (d:Director) ON (d.last_name)",
]

_NODE_COUNT_QUERY = """
    MATCH (n)
    RETURN labels(n) AS labels, count(*) AS cnt
    ORDER BY cnt DESC
"""

_EDGE_COUNT_QUERY = """
    MATCH ()-[r]->()
    RETURN type(r) AS type, count(*) AS cnt
    ORDER BY cnt DESC
"""

_VERIFY_QUERY = """
    MATCH (c:Company) RETURN 'Company' AS label, count(*) AS cnt
    UNION ALL
    MATCH (d:Director) RETURN 'Director' AS label, count(*) AS cnt
    UNION ALL
    MATCH (s:Shareholder) RETURN 'Shareholder' AS label, count(*) AS cnt
    UNION ALL
    MATCH (a:Address) RETURN 'Address' AS label, count(*) AS cnt
    UNION ALL
    MATCH (ind:Industry) RETURN 'Industry' AS label, count(*) AS cnt
    UNION ALL
    MATCH (t:TradingName) RETURN 'TradingName' AS label, count(*) AS cnt
    UNION ALL
    MATCH (i:Insolvency) RETURN 'Insolvency' AS label, count(*) AS cnt
    UNION ALL
    MATCH (ta:TradingArea) RETURN 'TradingArea' AS label, count(*) AS cnt
    UNION ALL
    MATCH ()-[r:IS]->() RETURN 'IS relationships' AS label, count(*) AS cnt
    UNION ALL
    MATCH ()-[r:RELATED_TO]->() RETURN 'RELATED_TO relationships' AS label, count(*) AS cnt
    UNION ALL
    MATCH ()-[r:IS_INVESTOR_DIRECTOR]->() RETURN 'IS_INVESTOR_DIRECTOR relationships' AS label, count(*) AS cnt
"""


def _log_graph_summary(repo: Neo4jRepository, *, label: str = "Graph summary") -> None:
    """Log node and edge counts broken down by label/type."""
    node_rows = repo.run_query(_NODE_COUNT_QUERY)
    edge_rows = repo.run_query(_EDGE_COUNT_QUERY)
    total_nodes = sum(r["cnt"] for r in node_rows)
    total_edges = sum(r["cnt"] for r in edge_rows)

    logger.info("--- %s ---", label)
    logger.info("  Total: %d nodes, %d edges", total_nodes, total_edges)

    if node_rows:
        logger.info("  Nodes by label:")
        for row in node_rows:
            label_str = ", ".join(row["labels"]) if isinstance(row["labels"], list) else row["labels"]
            logger.info("    %-30s %10d", label_str, row["cnt"])

    if edge_rows:
        logger.info("  Edges by type:")
        for row in edge_rows:
            logger.info("    %-30s %10d", row["type"], row["cnt"])


def drop_gds_graphs(repo: Neo4jRepository) -> None:
    """Drop all GDS in-memory graphs."""
    t0 = time.perf_counter()
    try:
        rows = repo.run_query(
            """
            CALL gds.graph.list() YIELD graphName
            WITH graphName
            CALL gds.graph.drop(graphName, false) YIELD graphName AS dropped
            RETURN count(dropped) AS graphs_dropped
            """,
        )
    except Exception as exc:  # noqa: BLE001
        elapsed = time.perf_counter() - t0
        logger.warning("Could not drop GDS graphs after %.2f s: %s", elapsed, exc)
    else:
        elapsed = time.perf_counter() - t0
        dropped = rows[0]["graphs_dropped"] if rows else 0
        logger.info("Dropped %d GDS graph(s) (%.2f s)", dropped, elapsed)


def delete_all_nodes(repo: Neo4jRepository) -> None:
    """Delete all nodes and relationships from the database."""
    _log_graph_summary(repo, label="Before delete")

    t0 = time.perf_counter()
    repo.run_query(
        """
        CALL apoc.periodic.iterate(
            'MATCH (n) RETURN n',
            'DETACH DELETE n',
            {batchSize: 50000, parallel: false, retries: 0}
        )
        """,
    )
    elapsed = time.perf_counter() - t0

    _log_graph_summary(repo, label="After delete")
    logger.info("Delete completed in %.2f s", elapsed)


def create_indexes(repo: Neo4jRepository) -> None:
    """Create all required indexes."""
    t0 = time.perf_counter()
    for idx in INDEXES:
        repo.run_query(idx)
    elapsed = time.perf_counter() - t0
    logger.info("Created %d indexes (%.2f s)", len(INDEXES), elapsed)


def load_csv(root_dir: Path | None = None, *, timeout: int = 12000) -> int:
    """Load CSV data via cypher-shell through docker compose.

    Args:
        root_dir: Project root directory.  Defaults to auto-detected repo root.
        timeout: Subprocess timeout in seconds.

    Returns:
        The cypher-shell exit code.

    """
    root = root_dir or SETTINGS.project_root
    script_path = root / "scripts" / "neo4j_load_csv.cypher"
    if not script_path.exists():
        logger.error("Script not found: %s", script_path)
        return 1

    user = SETTINGS.neo4j_user
    password = SETTINGS.neo4j_password

    logger.info("Executing cypher-shell with %s", script_path.name)
    t0 = time.perf_counter()
    with script_path.open() as fh:
        result = subprocess.run(  # noqa: S603
            [  # noqa: S607
                "docker",
                "compose",
                "exec",
                "-T",
                "neo4j",
                "cypher-shell",
                "-u",
                user,
                "-p",
                password,
            ],
            stdin=fh,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(root),
            check=False,
        )
    elapsed = time.perf_counter() - t0

    if result.stdout.strip():
        logger.info("stdout: %s", result.stdout[:2000])
    if result.stderr.strip():
        logger.info("stderr: %s", result.stderr[:2000])
    logger.info("cypher-shell finished with exit code %d (%.2f s)", result.returncode, elapsed)
    return result.returncode


def verify_import(repo: Neo4jRepository) -> list[dict]:
    """Verify the import by counting nodes and relationships.

    Returns:
        List of dicts with 'label' and 'cnt' keys.

    """
    rows = repo.run_query(_VERIFY_QUERY)
    logger.info("--- Import verification ---")
    for row in rows:
        logger.info("  %-30s %10d", row["label"], row["cnt"])
    return rows


def load_database(*, skip_load: bool = False, root_dir: Path | None = None) -> None:
    """Full drop-and-reload pipeline.

    Args:
        skip_load: Skip the CSV load step.
        root_dir: Project root for locating the cypher load script.

    Raises:
        RuntimeError: If connectivity check fails or CSV load returns non-zero.

    """
    pipeline_start = time.perf_counter()
    repo = Neo4jRepository(get_driver())

    if not repo.check_connectivity():
        msg = "Cannot connect to Neo4j"
        raise Neo4jConnectionError(msg)

    drop_gds_graphs(repo)
    delete_all_nodes(repo)
    create_indexes(repo)

    if not skip_load:
        rc = load_csv(root_dir=root_dir)
        if rc != 0:
            msg = f"cypher-shell exited with code {rc}"
            raise Neo4jConnectionError(msg)

    verify_import(repo)
    _log_graph_summary(repo, label="Final state")

    total_elapsed = time.perf_counter() - pipeline_start
    logger.info("Pipeline completed in %.2f s", total_elapsed)
