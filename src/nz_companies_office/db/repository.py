"""Neo4j repository — encapsulates Cypher query execution and connectivity."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING
from typing import Any
from typing import LiteralString

from nz_companies_office.exceptions import Neo4jConnectionError

if TYPE_CHECKING:
    from neo4j import Driver
    from neo4j import Query

logger = logging.getLogger(__name__)


class Neo4jRepository:
    """Wraps a Neo4j ``Driver`` and provides a clean query API.

    Encapsulates session management and connectivity checks so callers
    never deal with sessions directly.
    """

    def __init__(self, driver: Driver) -> None:
        """Initialise with an open Neo4j driver.

        Args:
            driver: An open Neo4j driver instance.

        """
        self._driver = driver

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_query(self, query: LiteralString | Query, **params: Any) -> list[dict]:  # noqa: ANN401
        """Execute a Cypher query and return results as a list of dicts.

        Args:
            query: Cypher query string.
            **params: Named query parameters.

        Returns:
            List of result records as dicts.

        """
        with self._driver.session() as session:
            return session.run(query, **params).data()

    def check_connectivity(self) -> bool:
        """Test that Neo4j is reachable.

        Returns:
            True if connected, False otherwise.

        """
        t0 = time.perf_counter()
        try:
            self.run_query("RETURN 1 AS ok")
        except Exception:
            logger.exception("Cannot connect to Neo4j")
            return False
        else:
            elapsed = time.perf_counter() - t0
            logger.info("Neo4j reachable (%.2f ms)", elapsed * 1000)
            return True

    def ensure_connected(self) -> None:
        """Verify Neo4j connectivity or raise.

        Raises:
            Neo4jConnectionError: If the connectivity check fails.

        """
        if not self.check_connectivity():
            msg = "Cannot connect to Neo4j"
            raise Neo4jConnectionError(msg)
