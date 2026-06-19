"""Neo4j database connection management."""

from __future__ import annotations

import os

from neo4j import Driver
from neo4j import GraphDatabase


class _Neo4jConnection:
    """Manages a singleton Neo4j driver instance."""

    _driver: Driver | None = None

    def get_driver(self) -> Driver:
        """Return the Neo4j driver, creating it if needed."""
        if self._driver is None:
            uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
            user = os.environ.get("NEO4J_USER", "neo4j")
            password = os.environ.get("NEO4J_PASSWORD", "password")
            self._driver = GraphDatabase.driver(uri, auth=(user, password))
        return self._driver

    def close_driver(self) -> None:
        """Close the Neo4j driver and reset the singleton."""
        if self._driver is not None:
            self._driver.close()
            self._driver = None


_connection = _Neo4jConnection()
get_driver = _connection.get_driver
close_driver = _connection.close_driver
