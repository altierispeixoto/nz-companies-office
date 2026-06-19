"""Integration test: fetch a real company from NZBN API and store in Neo4j."""

from __future__ import annotations

import os

import pytest

from nz_companies_office.clients.nzbn import NzbnClient
from nz_companies_office.db.connection import close_driver
from nz_companies_office.db.connection import get_driver
from nz_companies_office.db.repository import get_company_by_number
from nz_companies_office.db.repository import save_company


def _neo4j_reachable() -> bool:
    """Check if Neo4j is running at the configured URI."""
    try:
        uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        user = os.environ.get("NEO4J_USER", "neo4j")
        password = os.environ.get("NEO4J_PASSWORD", "password")
        from neo4j import GraphDatabase  # noqa: PLC0415

        with GraphDatabase.driver(uri, auth=(user, password)) as driver:
            driver.verify_connectivity()
    except Exception:  # noqa: BLE001
        return False
    else:
        return True


def _api_key_available() -> bool:
    """Check if an NZBN API subscription key is configured."""
    return bool(os.environ.get("NZBN_API_KEY"))


neo4j_not_ready = not _neo4j_reachable()
no_api_key = not _api_key_available()


@pytest.fixture(autouse=True)
def _cleanup_company() -> None:
    """Remove test data from Neo4j after the test."""
    yield
    driver = get_driver()
    with driver.session() as session:
        session.run(
            "MATCH (c:Company {company_number: $cn}) DETACH DELETE c",
            cn="3405451",
        )
    close_driver()


@pytest.mark.skipif(
    neo4j_not_ready or no_api_key,
    reason="Requires Neo4j running + NZBN_API_KEY set",
)
def test_fetch_and_store_company() -> None:
    """Fetch a real company from NZBN API, store in Neo4j, and retrieve it."""
    client = NzbnClient()
    company = client.get_company("3405451")

    assert company.name
    assert company.company_number == "3405451"
    assert company.nzbn

    save_company(company)

    retrieved = get_company_by_number("3405451")
    assert retrieved is not None
    assert retrieved.name == company.name
    assert retrieved.nzbn == company.nzbn
    assert len(retrieved.directors) > 0
    assert len(retrieved.addresses) > 0
