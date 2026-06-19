# ---
# marimo-version: 0.23.9
# license: Apache-2.0
# ---

import marimo

__generated_with = "0.23.9"
app = marimo.App(width="full")


@app.cell
def _():
    import subprocess
    import sys
    from pathlib import Path

    import marimo as mo

    sys.path.insert(0, str(Path.cwd() / "notebooks"))
    import _neo4j_helpers as nh

    root_dir = Path.cwd()
    return mo, nh, root_dir, subprocess


@app.cell
def _(mo, nh):
    h1 = mo.md("## Step 1: Check Neo4j Connectivity")

    try:
        nh.run_query("RETURN 1 AS ok").item(0, "ok")
        s1 = mo.md(":white_check_mark: Neo4j is reachable at `bolt://localhost:7687`")
    except Exception as e:
        s1 = mo.md(f":x: Cannot connect to Neo4j: {e}")
    return


@app.cell
def _(mo, nh):
    h2 = mo.md("## Step 2: Drop GDS In-Memory Graphs")

    try:
        r = nh.run_query(
            """
            CALL gds.graph.list() YIELD graphName
            WITH graphName
            CALL gds.graph.drop(graphName, false) YIELD graphName AS dropped
            RETURN count(dropped) AS graphs_dropped
            """,
        )
        dropped = r.item(0, "graphs_dropped") if len(r) > 0 else 0
        s2 = mo.md(f"**:white_check_mark:** Dropped {dropped} GDS in-memory graph(s)")
    except Exception as e:
        s2 = mo.md(f":warning: Could not drop GDS graphs: {e}")
    return


@app.cell
def _(mo, nh):
    h3 = mo.md("## Step 3: Delete All Nodes")

    try:
        nh.run_query(
            """
            CALL apoc.periodic.iterate(
                'MATCH (n) RETURN n',
                'DETACH DELETE n',
                {batchSize: 50000, parallel: false, retries: 0}
            )
            """,
        )
        remaining = nh.run_query("MATCH (n) RETURN count(*) AS c").item(0, "c")
        s3 = mo.md(f"**:white_check_mark:** Database cleaned. Remaining nodes: {remaining}")
    except Exception as e:
        s3 = mo.md(f":x: APOC periodic.iterate failed: {e}")
    return


@app.cell
def _(mo, nh):
    h4 = mo.md("## Step 4: Create Indexes")

    try:
        for idx in [
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
        ]:
            nh.run_query(idx)
        s4 = mo.md("**:white_check_mark:** All 12 indexes created")
    except Exception as e:
        s4 = mo.md(f":x: Index creation failed: {e}")
    return


@app.cell
def _(mo, root_dir, subprocess):
    h5 = mo.md("## Step 5: Load CSV Data")

    script_path = root_dir / "scripts" / "neo4j_load_csv.cypher"
    if not script_path.exists():
        s5 = mo.md(f":x: Script not found: {script_path}")
    else:
        with script_path.open() as f:
            result = subprocess.run(
                [
                    "docker",
                    "compose",
                    "exec",
                    "-T",
                    "neo4j",
                    "cypher-shell",
                    "-u",
                    "neo4j",
                    "-p",
                    "password",
                ],
                stdin=f,
                capture_output=True,
                text=True,
                timeout=600,
                cwd=root_dir,
            )
        s5 = mo.md(
            f"""
            **Exit code:** {result.returncode}

            **stdout:**
            ```
            {result.stdout[:2000]}
            ```

            **stderr:**
            ```
            {result.stderr[:2000]}
            ```
            """,
        )
    return


@app.cell
def _(mo, nh):
    h6 = mo.md("## Step 6: Verify Import")
    h6
    counts = nh.run_query(
        """
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
        """,
    )
    s6 = mo.md(f"### Node Counts\n\n{counts.to_pandas().to_markdown(index=False)}")
    s6
    return


@app.cell
def _(nh):
    t = nh.run_query("MATCH (n) RETURN count(*) AS c").item(0, "c")
    t
    return


if __name__ == "__main__":
    app.run()
