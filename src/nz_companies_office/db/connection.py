"""Neo4j database connection management."""

from __future__ import annotations

from neo4j import Driver
from neo4j import GraphDatabase

from nz_companies_office.config import SETTINGS


class _Neo4jConnection:
    """Manages a singleton Neo4j driver instance."""

    _driver: Driver | None = None

    def get_driver(self) -> Driver:
        """Return the Neo4j driver, creating it if needed."""
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                SETTINGS.neo4j_uri,
                auth=(SETTINGS.neo4j_user, SETTINGS.neo4j_password),
            )
        return self._driver

    def close_driver(self) -> None:
        """Close the Neo4j driver and reset the singleton."""
        if self._driver is not None:
            self._driver.close()
            self._driver = None


_connection = _Neo4jConnection()
get_driver = _connection.get_driver
close_driver = _connection.close_driver
