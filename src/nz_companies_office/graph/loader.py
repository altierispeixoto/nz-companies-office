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


_LOAD_STEP_SCRIPTS = [
    "00_setup",
    "01_companies",
    "02_directors",
    "03_shareholders",
    "04a_address_reg_office",
    "04b_address_service",
    "05_industries",
    "06_trading_names",
    "07_insolvencies",
    "08_properties",
    "09_trading_areas",
    "10_address_public",
    "11_corporate_links",
]

_STEP_COUNT_QUERIES: dict[str, str | None] = {
    "00_setup": None,
    "01_companies": "MATCH (c:Company) RETURN count(*) AS cnt",
    "02_directors": "MATCH ()-[r:DIRECTS]->() RETURN count(*) AS cnt",
    "03_shareholders": "MATCH ()-[r:HOLDS_SHARES_IN]->() RETURN count(*) AS cnt",
    "04a_address_reg_office": (
        "MATCH ()-[r:HAS_ADDRESS]->() WHERE r.address_type = 'REGISTERED_OFFICE' RETURN count(*) AS cnt"
    ),
    "04b_address_service": "MATCH ()-[r:HAS_ADDRESS]->() WHERE r.address_type = 'SERVICE' RETURN count(*) AS cnt",
    "05_industries": "MATCH (ind:Industry) RETURN count(*) AS cnt",
    "06_trading_names": "MATCH (t:TradingName) RETURN count(*) AS cnt",
    "07_insolvencies": "MATCH (i:Insolvency) RETURN count(*) AS cnt",
    "08_properties": None,
    "09_trading_areas": "MATCH (ta:TradingArea) RETURN count(*) AS cnt",
    "10_address_public": "MATCH ()-[r:HAS_ADDRESS]->() WHERE r.address_type = 'PUBLIC' RETURN count(*) AS cnt",
    "11_corporate_links": "MATCH ()-[r:IS]->() RETURN count(*) AS cnt",
}


def _cypher_shell_args(password: str, user: str) -> list[str]:
    """Build cypher-shell argument list for docker compose exec."""
    return [
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
    ]


def _format_count(n: int) -> str:
    """Format a count with comma separators."""
    return f"{n:,}"


def load_csv(
    root_dir: Path | None = None,
    *,
    timeout: int = 12000,
    repo: Neo4jRepository | None = None,
) -> int:
    """Load CSV data via cypher-shell through docker compose.

    Runs each per-step .cypher file sequentially, logging step-level timing
    and row counts.

    Args:
        root_dir: Project root directory.  Defaults to auto-detected repo root.
        timeout: Subprocess timeout in seconds per step.
        repo: Neo4j repository for pre/post count queries.  If provided, row
            counts are logged.

    Returns:
        0 on success, non-zero if any step fails.

    """
    root = root_dir or SETTINGS.project_root
    scripts_dir = root / "scripts" / "csv"
    if not scripts_dir.is_dir():
        logger.error("Scripts directory not found: %s", scripts_dir)
        return 1

    user = SETTINGS.neo4j_user
    password = SETTINGS.neo4j_password

    total_t0 = time.perf_counter()
    total_rows = 0
    for step_name in _LOAD_STEP_SCRIPTS:
        step_file = scripts_dir / f"{step_name}.cypher"
        if not step_file.exists():
            logger.error("Step file not found: %s", step_file)
            return 1

        count_query = _STEP_COUNT_QUERIES.get(step_name)
        before = 0
        if repo is not None and count_query is not None:
            result = repo.run_query(count_query)
            before = result[0]["cnt"] if result else 0

        logger.info(
            "  %s %s",
            step_name.replace("_", " ").title(),
            "." * max(1, 40 - len(step_name)),
        )
        t0 = time.perf_counter()
        result = subprocess.run(  # noqa: S603
            _cypher_shell_args(password, user),
            stdin=step_file.open(),
            capture_output=True,
            text=True,
            cwd=str(root),
            timeout=timeout,
            check=False,
        )
        elapsed = time.perf_counter() - t0

        if result.stderr.strip():
            for line in result.stderr.strip().splitlines():
                if "Received notification from DBMS server" in line:
                    logger.debug("Neo4j notification: %s", line[:200])
                else:
                    logger.info("    stderr: %s", line)

        if result.returncode != 0:
            logger.error(
                "  %s FAILED after %.1f s (rc=%d)",
                step_name.replace("_", " ").title(),
                elapsed,
                result.returncode,
            )
            return result.returncode

        if repo is not None and count_query is not None:
            result = repo.run_query(count_query)
            after = result[0]["cnt"] if result else 0
            delta = after - before
            total_rows += delta
            logger.info(
                "  \u2514\u2500 %s rows in %.1f s",
                _format_count(delta),
                elapsed,
            )
        else:
            logger.info("  \u2514\u2500 done in %.1f s", elapsed)

    total_elapsed = time.perf_counter() - total_t0
    logger.info(
        "\u250c\u2500\u2500 %s total rows loaded \u2500\u2500 %.1f s \u2500\u2500\u2510",
        _format_count(total_rows),
        total_elapsed,
    )
    return 0


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
        rc = load_csv(root_dir=root_dir, repo=repo)
        if rc != 0:
            msg = f"cypher-shell exited with code {rc}"
            raise Neo4jConnectionError(msg)

    verify_import(repo)
    _log_graph_summary(repo, label="Final state")

    total_elapsed = time.perf_counter() - pipeline_start
    logger.info("Pipeline completed in %.2f s", total_elapsed)
