"""Neo4j repository for NZ company entities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nz_companies_office.models.company import Address
from nz_companies_office.models.company import Company
from nz_companies_office.models.company import Director
from nz_companies_office.models.company import Shareholder

if TYPE_CHECKING:
    from neo4j import Driver
    from neo4j import Transaction


def save_company(driver: Driver, company: Company) -> None:
    """Create or merge a Company node in Neo4j.

    Args:
        driver: Neo4j driver instance.
        company: Company model to persist.
    """
    with driver.session() as session:
        session.execute_write(_create_company_node, company)
        for address in company.addresses:
            session.execute_write(_create_address_node, company.company_number, address)
        for director in company.directors:
            session.execute_write(_create_director_relationship, company.company_number, director)
        for shareholder in company.shareholders:
            session.execute_write(
                _create_shareholder_relationship,
                company.company_number,
                shareholder,
            )


def get_company_by_number(driver: Driver, company_number: str) -> Company | None:
    """Retrieve a company by its Companies Office number.

    Args:
        driver: Neo4j driver instance.
        company_number: The company number to look up.

    Returns:
        Company model if found, None otherwise.
    """
    with driver.session() as session:
        return session.execute_read(_query_company_node, company_number)


def _create_company_node(tx: Transaction, company: Company) -> None:
    """Create or merge a Company node within a transaction."""
    query = """
    MERGE (c:Company {company_number: $company_number})
    SET c.name = $name,
        c.status = $status,
        c.entity_type = $entity_type,
        c.incorporation_date = $incorporation_date,
        c.nzbn = $nzbn
    """
    tx.run(
        query,
        company_number=company.company_number,
        name=company.name,
        status=company.status.value,
        entity_type=company.entity_type,
        incorporation_date=(company.incorporation_date.isoformat() if company.incorporation_date else None),
        nzbn=company.nzbn,
    )


def _create_address_node(tx: Transaction, company_number: str, address: Address) -> None:
    """Create or merge an Address node and link to its company."""
    query = """
    MERGE (a:Address {
        street: $street,
        city: COALESCE($city, ''),
        country: COALESCE($country, '')
    })
    SET a.suburb = $suburb,
        a.postcode = $postcode
    WITH a
    MATCH (c:Company {company_number: $company_number})
    MERGE (c)-[r:HAS_ADDRESS]->(a)
    SET r.address_type = $address_type
    """
    tx.run(
        query,
        company_number=company_number,
        address_type=address.address_type.value,
        street=address.street,
        suburb=address.suburb,
        city=address.city,
        postcode=address.postcode,
        country=address.country,
    )


def _create_director_relationship(tx: Transaction, company_number: str, director: Director) -> None:
    """Create or merge a Director node and link to its company."""
    query = """
    MERGE (d:Director {name: $name})
    SET d.role = $role,
        d.appointment_date = $appointment_date
    WITH d
    MATCH (c:Company {company_number: $company_number})
    MERGE (d)-[:DIRECTS]->(c)
    """
    tx.run(
        query,
        company_number=company_number,
        name=director.name,
        role=director.role,
        appointment_date=(director.appointment_date.isoformat() if director.appointment_date else None),
    )


def _create_shareholder_relationship(tx: Transaction, company_number: str, shareholder: Shareholder) -> None:
    """Create or merge a Shareholder node and link to its company."""
    query = """
    MERGE (s:Shareholder {name: $name})
    SET s.share_count = $share_count,
        s.share_type = $share_type
    WITH s
    MATCH (c:Company {company_number: $company_number})
    MERGE (s)-[:HOLDS_SHARES_IN]->(c)
    """
    tx.run(
        query,
        company_number=company_number,
        name=shareholder.name,
        share_count=shareholder.share_count,
        share_type=shareholder.share_type,
    )


def _query_company_node(tx: Transaction, company_number: str) -> Company | None:
    """Retrieve a company and its related nodes."""
    query = """
    MATCH (c:Company {company_number: $company_number})
    OPTIONAL MATCH (d:Director)-[:DIRECTS]->(c)
    OPTIONAL MATCH (s:Shareholder)-[:HOLDS_SHARES_IN]->(c)
    OPTIONAL MATCH (c)-[r:HAS_ADDRESS]->(a:Address)
    RETURN c,
           collect(DISTINCT d) AS directors,
           collect(DISTINCT s) AS shareholders,
           collect(DISTINCT {address: a, address_type: r.address_type}) AS addresses
    """
    result = tx.run(query, company_number=company_number)
    record = result.single()
    if record is None:
        return None

    node = record["c"]
    directors = [_parse_director_node(n) for n in record["directors"] if n is not None]
    shareholders = [_parse_shareholder_node(n) for n in record["shareholders"] if n is not None]
    addresses = [_parse_address_entry(entry) for entry in record["addresses"] if entry is not None]

    return Company(
        company_number=node["company_number"],
        name=node["name"],
        status=node.get("status", ""),
        entity_type=node.get("entity_type"),
        incorporation_date=node.get("incorporation_date"),
        nzbn=node.get("nzbn"),
        directors=directors,
        shareholders=shareholders,
        addresses=addresses,
    )


def _parse_director_node(node: dict) -> Director:
    return Director(
        name=node.get("name", ""),
        role=node.get("role"),
        appointment_date=node.get("appointment_date"),
    )


def _parse_shareholder_node(node: dict) -> Shareholder:
    return Shareholder(
        name=node.get("name", ""),
        share_count=int(node.get("share_count", 0)),
        share_type=node.get("share_type"),
    )


def _parse_address_entry(entry: dict) -> Address:
    node = entry["address"]
    return Address(
        address_type=entry.get("address_type", ""),
        street=node.get("street", ""),
        suburb=node.get("suburb"),
        city=node.get("city"),
        postcode=node.get("postcode"),
        country=node.get("country", ""),
    )
