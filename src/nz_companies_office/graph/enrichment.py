"""Post-load enrichment: compute share percentages and majority flags."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING
from typing import LiteralString

from neo4j import Query

from nz_companies_office.db.connection import get_driver

if TYPE_CHECKING:
    from neo4j import Driver

logger = logging.getLogger(__name__)

_SHARE_PERCENTAGE_QUERY = """
    MATCH (c:Company)
    WHERE EXISTS { MATCH ()-[:HOLDS_SHARES_IN]->(c) }
    WITH c
    OPTIONAL MATCH (s:Shareholder)-[r:HOLDS_SHARES_IN]->(c)
    WITH c, sum(r.shares) AS total_shares
    WHERE total_shares > 0
    WITH c, total_shares
    MATCH (s:Shareholder)-[r:HOLDS_SHARES_IN]->(c)
    SET r.share_percentage = CASE
            WHEN total_shares > 0
            THEN toFloat(r.shares) / total_shares * 100.0
            ELSE 0.0
        END,
        r.is_majority = CASE
            WHEN toFloat(r.shares) / total_shares > 0.5
            THEN true
            ELSE false
        END,
        c.total_shares = total_shares
    RETURN count(*) AS updated
"""


def compute_share_percentages(driver: Driver | None = None) -> int:
    """Compute share percentages and majority flags on HOLDS_SHARES_IN edges.

    For each company, sums all shares across its shareholders, then sets
    ``share_percentage`` and ``is_majority`` on each HOLDS_SHARES_IN
    relationship.  Also stores ``total_shares`` on the Company node.

    Args:
        driver: Neo4j driver instance.  Uses the default connection when None.

    Returns:
        Count of relationships updated.

    """
    t0 = time.perf_counter()
    if driver is None:
        driver = get_driver()
    result = _run_query(driver, _SHARE_PERCENTAGE_QUERY)
    elapsed = time.perf_counter() - t0
    updated = result[0]["updated"] if result else 0
    logger.info("Share percentages: %d relationships updated (%.2f s)", updated, elapsed)
    return updated


def _run_query(driver: Driver, query: LiteralString | Query) -> list[dict]:
    """Execute a Cypher query and return the results as a list of dicts."""
    with driver.session() as session:
        return session.run(query).data()
