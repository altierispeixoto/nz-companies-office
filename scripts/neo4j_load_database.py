#!/usr/bin/env python3
"""Drop and reload the Neo4j company-register graph."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from neo4j import GraphDatabase

URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
USER = os.environ.get("NEO4J_USER", "neo4j")
PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")
ROOT_DIR = Path(__file__).resolve().parent.parent

INDEXES = [
    "CREATE INDEX company_nzbn IF NOT EXISTS FOR (c:Company) ON (c.nzbn)",
    "CREATE INDEX company_number_idx IF NOT EXISTS FOR (c:Company) ON (c.company_number)",
    "CREATE INDEX director_name_idx IF NOT EXISTS FOR (d:Director) ON (d.name)",
    "CREATE INDEX shareholder_name_idx IF NOT EXISTS FOR (s:Shareholder) ON (s.name)",
    "CREATE INDEX address_key_idx IF NOT EXISTS FOR (a:Address) ON (a.address_type, a.street, a.city, a.country)",
    "CREATE INDEX industry_code_idx IF NOT EXISTS FOR (ind:Industry) ON (ind.code)",
    "CREATE INDEX trading_name_idx IF NOT EXISTS FOR (t:TradingName) ON (t.name)",
    "CREATE INDEX insolvency_idx IF NOT EXISTS FOR (i:Insolvency) ON (i.type, i.appointment_type, i.appointee)",
    "CREATE INDEX trading_area_idx IF NOT EXISTS FOR (ta:TradingArea) ON (ta.name)",
    "CREATE INDEX company_name_idx IF NOT EXISTS FOR (c:Company) ON (c.name)",
    "CREATE INDEX shareholder_surname_idx IF NOT EXISTS FOR (s:Shareholder) ON (s.surname)",
    "CREATE INDEX director_last_name_idx IF NOT EXISTS FOR (d:Director) ON (d.last_name)",
]

VERIFY_QUERY = """
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


def run_query(driver: GraphDatabase.driver, q: str) -> list[dict]:  # noqa: D103
    with driver.session() as s:
        return s.run(q).data()


def step1_check_connectivity(driver: GraphDatabase.driver) -> bool:  # noqa: D103
    print("Step 1: Check Neo4j connectivity")  # noqa: T201
    try:
        run_query(driver, "RETURN 1 AS ok")
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ Cannot connect to Neo4j: {e}")  # noqa: T201
        return False
    else:
        print(f"  ✓ Neo4j reachable at {URI}")  # noqa: T201
        return True


def step2_drop_gds_graphs(driver: GraphDatabase.driver) -> None:  # noqa: D103
    print("Step 2: Drop GDS in-memory graphs")  # noqa: T201
    try:
        r = run_query(
            driver,
            """
            CALL gds.graph.list() YIELD graphName
            WITH graphName
            CALL gds.graph.drop(graphName, false) YIELD graphName AS dropped
            RETURN count(dropped) AS graphs_dropped
            """,
        )
    except Exception as e:  # noqa: BLE001
        print(f"  ⚠ Could not drop GDS graphs: {e}")  # noqa: T201
    else:
        dropped = r[0]["graphs_dropped"] if r else 0
        print(f"  ✓ Dropped {dropped} GDS graph(s)")  # noqa: T201


def step3_delete_all_nodes(driver: GraphDatabase.driver) -> None:  # noqa: D103
    print("Step 3: Delete all nodes")  # noqa: T201
    run_query(
        driver,
        """
        CALL apoc.periodic.iterate(
            'MATCH (n) RETURN n',
            'DETACH DELETE n',
            {batchSize: 50000, parallel: false, retries: 0}
        )
        """,
    )
    remaining = run_query(driver, "MATCH (n) RETURN count(*) AS c")[0]["c"]
    print(f"  ✓ Database cleaned. Remaining nodes: {remaining}")  # noqa: T201


def step4_create_indexes(driver: GraphDatabase.driver) -> None:  # noqa: D103
    print("Step 4: Create indexes")  # noqa: T201
    for idx in INDEXES:
        run_query(driver, idx)
    print(f"  ✓ All {len(INDEXES)} indexes created")  # noqa: T201


def step5_load_csv() -> int:  # noqa: D103
    print("Step 5: Load CSV data")  # noqa: T201
    script_path = ROOT_DIR / "scripts" / "neo4j_load_csv.cypher"
    if not script_path.exists():
        print(f"  ✗ Script not found: {script_path}")  # noqa: T201
        return 1

    with script_path.open() as f:
        result = subprocess.run(  # noqa: S603
            [  # noqa: S607
                "docker",
                "compose",
                "exec",
                "-T",
                "neo4j",
                "cypher-shell",
                "-u",
                USER,
                "-p",
                PASSWORD,
            ],
            stdin=f,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(ROOT_DIR),
            check=False,
        )

    if result.stdout.strip():
        print("  stdout:", result.stdout[:2000])  # noqa: T201
    if result.stderr.strip():
        print("  stderr:", result.stderr[:2000])  # noqa: T201
    print(f"  Exit code: {result.returncode}")  # noqa: T201
    return result.returncode


def step6_verify(driver: GraphDatabase.driver) -> None:  # noqa: D103
    print("Step 6: Verify import")  # noqa: T201
    rows = run_query(driver, VERIFY_QUERY)
    print(f"  {'Label':<30} {'Count':>10}")  # noqa: T201
    print("  " + "-" * 42)  # noqa: T201
    for row in rows:
        print(f"  {row['label']:<30} {row['cnt']:>10,}")  # noqa: T201


def main() -> None:  # noqa: D103
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-load", action="store_true", help="skip the CSV load step")
    args = parser.parse_args()

    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

    if not step1_check_connectivity(driver):
        sys.exit(1)

    step2_drop_gds_graphs(driver)
    step3_delete_all_nodes(driver)
    step4_create_indexes(driver)

    if not args.skip_load:
        rc = step5_load_csv()
        if rc != 0:
            sys.exit(rc)

    step6_verify(driver)
    driver.close()
    print("\nDone.")  # noqa: T201


if __name__ == "__main__":
    main()
