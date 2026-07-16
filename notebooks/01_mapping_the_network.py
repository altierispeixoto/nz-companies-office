# ---
# marimo-version: 0.23.9
# license: Apache-2.0
# ---

import marimo

__generated_with = "0.23.10"
app = marimo.App(width="full")


@app.cell
def _():
    import sys
    from pathlib import Path

    import marimo as mo

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import _neo4j_helpers as nh

    return mo, nh


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Mapping New Zealand's Corporate Network

    **[New Zealand's Companies Office](https://www.companiesoffice.govt.nz/) holds over 1.8 million companies, from
    the corner dairy to multinational subsidiaries.
    This notebook maps the raw
    landscape before we dive into who owns what, and who sits on which board.**

    *NZ Companies Office data (June 2026).*
    """)
    return


@app.cell
def _(mo, nh):
    mo.md(
        f"""
        ## Graph Overview

        The graph has **{nh.run_query("MATCH (n) RETURN count(*) AS c").item(0, "c"):,} nodes**
        and **{nh.run_query("MATCH ()-[r]->() RETURN count(*) AS c").item(0, "c"):,} relationships**
        spread across these labels:
        """,
    )
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (n)
        RETURN labels(n)[0] AS label,
               count(*) AS nodes
        ORDER BY nodes DESC
        """,
        page_size=15,
    )
    return


@app.cell
def _(mo, nh):
    mo.md(
        f"""
        **{nh.run_query("MATCH (c:Company) RETURN count(*) AS c").item(0, "c"):,} companies** form
        the core of this graph. Each company has a status (registered or removed),
        an entity type (NZ Limited, Overseas Company, etc.), and most have a New
        Zealand Business Number (NZBN).

        ### Relationship types
        """,
    )
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH ()-[r]->()
        RETURN type(r) AS relationship,
               count(*) AS count
        ORDER BY count DESC
        """,
        page_size=10,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Top shareholders by reach

    Which entities appear in the most *different* companies? This reveals
    institutional players, professional trustees, and — potentially —
    nominee/director-for-hire operations.
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (s:Shareholder)-[:HOLDS_SHARES_IN]->(c:Company)
        RETURN s.name AS shareholder,
               count(DISTINCT c) AS companies,
               collect(DISTINCT c.name)[0..10] AS examples
        ORDER BY companies DESC
        LIMIT 20
        """,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Immediately we see **trustee and custodian entities dominate the top 20**.
    "NEW ZEALAND TRUSTEE SERVICES LIMITED" appears in 659 companies. These
    aren't active investors — they're professional trustees providing a
    registered office service. The first individual name doesn't appear until much further down the list.

    ### The most sought-after directors
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (d:Director)-[:DIRECTS]->(c:Company)
        RETURN d.name AS director,
               count(DISTINCT c) AS companies,
               collect(DISTINCT c.name)[0..3] AS examples
        ORDER BY companies DESC
        LIMIT 15
        """,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Director positions are highly concentrated at the top. **665 directorships
    is the maximum** (Bronwyn Ann HANTZ — likely a professional nominee),
    but the **median is just 1** and the **mean is 1.73**. Most directors
    sit on a single board; a tiny tail holds hundreds of positions.

    ### Director seat distribution
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (d:Director)-[:DIRECTS]->(c:Company)
        WITH d, count(DISTINCT c) AS companies
        RETURN CASE
            WHEN companies = 1 THEN '1 company'
            WHEN companies <= 5 THEN '2–5 companies'
            WHEN companies <= 20 THEN '6–20 companies'
            WHEN companies <= 100 THEN '21–100 companies'
            ELSE '100+ companies'
        END AS seat_bucket,
        count(*) AS directors,
        sum(companies) AS total_seats
        ORDER BY total_seats DESC
        """,
    )
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (d:Director)-[:DIRECTS]->(c:Company)
        WITH d, count(DISTINCT c) AS companies
        RETURN min(companies) AS min,
               max(companies) AS max,
               round(avg(companies), 2) AS avg,
               percentileCont(companies, 0.5) AS median
        """,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Most shareholders per company
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (s:Shareholder)-[:HOLDS_SHARES_IN]->(c:Company)
        RETURN c.name AS company,
               count(DISTINCT s) AS shareholders
        ORDER BY shareholders DESC
        LIMIT 15
        """,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    "The Combined Buildings Supplies co-operative" has 484 co-owners. [combinedbuildingsupplies](https://combinedbuildingsupplies.com/)

    ### Entity type distribution
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (c:Company)
        RETURN c.entity_type AS entity_type,
               count(*) AS count
        ORDER BY count DESC
        """,
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    ### Status breakdown
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (c:Company)
        RETURN c.status AS status,
               count(*) AS count
        ORDER BY count DESC
        """,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Co-investment Graph

    To understand the network structure, we first build the co-investment graph:
    two shareholders are connected if they both hold shares in the same company,
    weighted by the number of shared companies. This is projected as a GDS
    in-memory graph for graph algorithms like WCC (weakly connected components).
    """)
    return


@app.cell
def _(mo, nh):
    ### CALL gds.graph.drop('coinvest')

    exists = nh.run_query(
        "CALL gds.graph.exists('coinvest') YIELD exists RETURN exists",
    ).item(0, "exists")

    if not exists:
        # Create CO_INVESTS_WITH edges for pairs with >= 5 shared companies
        nh.run_query(
            """
            MATCH (s1:Shareholder)-[:HOLDS_SHARES_IN]->(c:Company)<-[:HOLDS_SHARES_IN]-(s2:Shareholder)
            WHERE elementId(s1) < elementId(s2)
            WITH s1, s2, count(DISTINCT c) AS shared_companies
            WHERE shared_companies >= 5
            MERGE (s1)-[r:CO_INVESTS_WITH]-(s2)
            SET r.weight = shared_companies
            """,
        )
        # Project into GDS
        nh.run_query(
            """
            CALL gds.graph.project(
              'coinvest',
              'Shareholder',
              {
                CO_INVESTS_WITH: {
                  orientation: 'UNDIRECTED',
                  properties: ['weight']
                }
              }
            )
            """,
        )
        result_display = mo.md("**:white_check_mark:** `coinvest` graph created")
    else:
        result_display = mo.md("✅ `coinvest` graph already exists")
    result_display
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### A fragmented network

    **Weakly Connected Components (WCC)** is a graph algorithm that finds
    islands of connectivity: two nodes are in the same component if there's
    *any* path between them, ignoring edge direction. The co-investment graph
    is undirected (if A co-invests with B, B co-invests with A), so WCC
    identifies every cluster of investors who are connected through their
    shared company holdings — and the vast majority that are completely
    isolated.
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        CALL gds.wcc.stream('coinvest')
        YIELD nodeId, componentId
        RETURN componentId, count(*) AS size
        ORDER BY size DESC
        LIMIT 10
        """,
    )
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        // Shareholders with co-investors (in the GDS projection)
        MATCH (s:Shareholder)
        WHERE EXISTS { MATCH (s)-[:CO_INVESTS_WITH]-() }
        RETURN 'Shareholders in coinvest graph' AS metric, count(*) AS value
        UNION ALL
        // Shareholders without co-investors (each is its own singleton component)
        MATCH (s:Shareholder)
        WHERE NOT EXISTS { MATCH (s)-[:CO_INVESTS_WITH]-() }
        RETURN 'Isolated shareholders (singleton components)' AS metric, count(*) AS value
        """,
    )
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        // Top components reconstructed by manual traversal
        MATCH (anchor:Shareholder)
        WHERE EXISTS { MATCH (anchor)-[:CO_INVESTS_WITH]-() }
        WITH anchor, rand() AS r
        ORDER BY r
        LIMIT 10
        MATCH path = shortestPath((anchor)-[:CO_INVESTS_WITH*..10]-(other))
        WHERE anchor <> other
        WITH anchor, other
        ORDER BY other.name
        WITH anchor,
             count(DISTINCT other) AS component_size,
             apoc.text.join(collect(DISTINCT other.name)[0..30], ', ') AS coinvestors_sample
        WHERE component_size >= 5
        RETURN anchor.name AS anchor, component_size, coinvestors_sample
        ORDER BY component_size DESC
        """,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### The Otorohanga Cluster

    Beyond the co-investment graph, another striking pattern emerges from
    registered addresses. **1,085 companies** share a single registered address:
    **18 Maniapoto Street, Otorohanga** — the Bailey Ingham Trustees network,
    a trustee services firm providing registered office and directorship
    services at industrial scale.
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (c:Company)-[r:HAS_ADDRESS]->(a:Address)
        WHERE toLower(a.street) CONTAINS '18 maniapoto' AND r.address_type = 'REGISTERED_OFFICE'
        WITH a, count(DISTINCT c) AS companies
        RETURN a.street AS address, a.city AS city, companies
        ORDER BY companies DESC
        LIMIT 10
        """,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    The same pattern repeats at **93 Maniapoto Street** (265 companies) and
    at other trustee-firm addresses. These aren't real offices — they're the
    registered addresses used by professional trustee companies that provide
    corporate secretarial and directorship services to thousands of entities.

    This is notable because **1,085 companies at one address** means 1,085
    distinct legal entities that almost certainly share the same beneficial
    ownership or administration. It's a flag for nominee structures, not a
    sign of fraud — but it's exactly the kind of pattern that graph analysis
    surfaces immediately.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Trading names — how many companies share a brand?

    A trading name is a brand or business name a company operates under,
    separate from its legal name. A single trading name can be used by
    multiple companies — a franchise brand like "Liquorland" or a real
    estate agency chain. How common is this sharing?
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (t:TradingName)<-[:TRADES_AS]-(c:Company)
        WITH t, count(DISTINCT c) AS companies
        RETURN CASE
            WHEN companies = 1 THEN '1 company'
            WHEN companies <= 5 THEN '2–5 companies'
            WHEN companies <= 20 THEN '6–20 companies'
            WHEN companies <= 100 THEN '21–100 companies'
            ELSE '100+ companies'
        END AS sharing_bucket,
        count(*) AS trading_names,
        sum(companies) AS total_company_uses
        ORDER BY total_company_uses DESC
        """,
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    And which are the most-shared trading names?
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (t:TradingName)<-[:TRADES_AS]-(c:Company)
        WITH t, collect(DISTINCT c.name) AS names, count(DISTINCT c) AS companies
        WHERE companies > 1
        RETURN t.name AS trading_name,
               companies,
               names[0..5] AS examples
        ORDER BY companies DESC
        LIMIT 15
        """,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Cleanup

    Drop the in-memory `coinvest` graph and delete `CO_INVESTS_WITH` relationships
    to free memory before moving to the next notebook.
    """)
    return


@app.cell
def _(mo, nh):
    e = nh.run_query(
        "CALL gds.graph.exists('coinvest') YIELD exists RETURN exists",
    ).item(0, "exists")

    if e:
        nh.run_query("CALL gds.graph.drop('coinvest', false)")
        dropped = 1
    else:
        dropped = 0

    nh.run_query(
        """
        CALL apoc.periodic.iterate(
            'MATCH (s1:Shareholder)-[r:CO_INVESTS_WITH]-(s2:Shareholder) RETURN r',
            'DELETE r',
            {batchSize: 50000, parallel: false}
        )
        """,
    )

    mo.md(f"**:white_check_mark:** Dropped {dropped} GDS graph(s), deleted CO_INVESTS_WITH relationships")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Key Takeaways

    1. **Nominee directors at scale** — the top director holds 665 seats, but 50%
       of directors sit on exactly one board. The distribution is a long tail:
       a tiny cohort of professional nominees vs. millions of single-company
       directors.
    2. **Address-based nominee clusters** — 1,085 companies share a single
       registered office at 18 Maniapoto Street, Otorohanga (Bailey Ingham
       Trustees). Address aggregation is the most direct signal of nominee
       operations.
    3. **Co-investment is fragmented** — 897K of 900K WCC components are
       singletons. Most shareholders co-invest with nobody (above the threshold
       of 5 shared companies). The few real clusters (max size 183) are the
       interesting signal.
    4. **Trading names are mostly unique** — 93% of trading names belong to
       a single company. Shared trading names are rare and mainly trustee
       service brands.

    Up next: **[02: Co-investment Patterns](http://localhost:2718/?file=02_co_investment_patterns.py)** —
    who actually invests together, trustee "black boxes," and suspicious clusters.
    """)
    return


if __name__ == "__main__":
    app.run()
