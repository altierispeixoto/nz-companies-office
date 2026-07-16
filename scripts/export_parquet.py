"""Export Neo4j data to parquet files for DuckDB-WASM."""

from __future__ import annotations

import datetime
import os
from collections.abc import Callable

import pyarrow as pa
import pyarrow.parquet as pq
from neo4j import GraphDatabase

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")
OUT_DIR = os.environ.get("PARQUET_OUT_DIR", "app/public")

BATCH_SIZE = 100000


def _to_date(val) -> datetime.date | None:
    """Convert Neo4j Date to Python date."""
    if val is None:
        return None
    if isinstance(val, datetime.date):
        return val
    return datetime.date(val.year, val.month, val.day)


def export_companies(driver: GraphDatabase.driver, out_path: str) -> None:
    query = """
        MATCH (c:Company)
        RETURN c.company_number AS company_number,
               c.name AS name,
               c.status AS status,
               c.nzbn AS nzbn,
               c.entity_type AS entity_type,
               c.incorporation_date AS incorporation_date,
               c.removal_date AS removal_date
        ORDER BY c.company_number
    """
    schema = pa.schema([
        ("company_number", pa.string()),
        ("name", pa.string()),
        ("status", pa.string()),
        ("nzbn", pa.string()),
        ("entity_type", pa.string()),
        ("incorporation_date", pa.date32()),
        ("removal_date", pa.date32()),
    ])
    _export_table(driver, query, schema, out_path, "companies.parquet", _convert_company_row)
    print("  companies.parquet done")


def export_shareholders(driver: GraphDatabase.driver, out_path: str) -> None:
    query = """
        MATCH (s:Shareholder)
        RETURN s.name AS name,
               s.sh_type AS sh_type,
               s.surname AS surname,
               s.first_initial AS first_initial
        ORDER BY s.name
    """
    schema = pa.schema([
        ("name", pa.string()),
        ("sh_type", pa.string()),
        ("surname", pa.string()),
        ("first_initial", pa.string()),
    ])
    _export_table(driver, query, schema, out_path, "shareholders.parquet")
    print("  shareholders.parquet done")


def export_holdings(driver: GraphDatabase.driver, out_path: str) -> None:
    query = """
        MATCH (s:Shareholder)-[r:HOLDS_SHARES_IN]->(c:Company)
        RETURN s.name AS shareholder_name,
               c.company_number AS company_number,
               r.shares AS shares,
               r.extensive_shareholding AS extensive_shareholding,
               r.start_date AS start_date,
               r.sh_status AS sh_status
        ORDER BY s.name, c.company_number
    """
    schema = pa.schema([
        ("shareholder_name", pa.string()),
        ("company_number", pa.string()),
        ("shares", pa.int64()),
        ("extensive_shareholding", pa.bool_()),
        ("start_date", pa.date32()),
        ("sh_status", pa.string()),
    ])
    _export_table(driver, query, schema, out_path, "holdings.parquet", _convert_holding_row)
    print("  holdings.parquet done")


def _convert_company_row(r: dict) -> dict:
    return {
        "company_number": r.get("company_number"),
        "name": r.get("name"),
        "status": r.get("status"),
        "nzbn": r.get("nzbn"),
        "entity_type": r.get("entity_type"),
        "incorporation_date": _to_date(r.get("incorporation_date")),
        "removal_date": _to_date(r.get("removal_date")),
    }


def _convert_holding_row(r: dict) -> dict:
    return {
        "shareholder_name": r.get("shareholder_name"),
        "company_number": r.get("company_number"),
        "shares": r.get("shares"),
        "extensive_shareholding": r.get("extensive_shareholding"),
        "start_date": _to_date(r.get("start_date")),
        "sh_status": r.get("sh_status"),
    }


def _export_table(
    driver: GraphDatabase.driver,
    query: str,
    schema: pa.Schema,
    out_path: str,
    filename: str,
    convert_row: Callable[[dict], dict] | None = None,
) -> None:
    os.makedirs(out_path, exist_ok=True)
    filepath = os.path.join(out_path, filename)

    with driver.session() as session:
        result = session.run(query)
        writer = None
        try:
            batch_rows: list[dict] = []
            for record in result:
                row = record.data()
                if convert_row:
                    row = convert_row(row)
                batch_rows.append(row)
                if len(batch_rows) >= BATCH_SIZE:
                    table = pa.Table.from_pylist(batch_rows, schema=schema)
                    if writer is None:
                        writer = pq.ParquetWriter(filepath, schema)
                    writer.write_table(table)
                    batch_rows = []
            if batch_rows:
                table = pa.Table.from_pylist(batch_rows, schema=schema)
                if writer is None:
                    writer = pq.ParquetWriter(filepath, schema)
                writer.write_table(table)
        finally:
            if writer:
                writer.close()


def export_industries(driver: GraphDatabase.driver, out_path: str) -> None:
    query = """
        MATCH (c:Company)-[:HAS_INDUSTRY]->(ind:Industry)
        RETURN c.company_number AS company_number,
               ind.code AS industry_code,
               ind.description AS industry_description
        ORDER BY c.company_number
    """
    schema = pa.schema([
        ("company_number", pa.string()),
        ("industry_code", pa.string()),
        ("industry_description", pa.string()),
    ])
    _export_table(driver, query, schema, out_path, "industry.parquet")
    print("  industry.parquet done")


def export_industry_codes(driver: GraphDatabase.driver, out_path: str) -> None:
    query = """
        MATCH (ind:Industry)
        RETURN ind.code AS code,
               ind.description AS description
        ORDER BY ind.description
    """
    schema = pa.schema([
        ("code", pa.string()),
        ("description", pa.string()),
    ])
    _export_table(driver, query, schema, out_path, "industry_codes.parquet")
    print("  industry_codes.parquet done")


def main() -> None:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        print("Exporting companies...")
        export_companies(driver, OUT_DIR)
        print("Exporting shareholders...")
        export_shareholders(driver, OUT_DIR)
        print("Exporting holdings...")
        export_holdings(driver, OUT_DIR)
        print("Exporting industries...")
        export_industries(driver, OUT_DIR)
        export_industry_codes(driver, OUT_DIR)
        print(f"Done. Files written to {OUT_DIR}/")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
