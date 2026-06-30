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
    # Co-investment Patterns: Trustees, Nominees, and Syndicates

    **In the first notebook we saw the graph's size and structure. Now we
    follow the money — and the names. Who invests alongside whom? Which
    entities sit in hundreds of companies but never share a co-investor?
    And what does a nominee network look like in practice?**

    We'll explore co-investor pairs, tight syndicates (triangles), the
    notorious trustee "black boxes," and the suspicious clusters that
    point to nominee/director-for-hire operations.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## The Most Frequent Co-investor Pairs

    Which two shareholders appear together in the most companies?
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (s1:Shareholder)-[:HOLDS_SHARES_IN]->(c:Company {status:'REGISTERED'})<-[:HOLDS_SHARES_IN]-(s2:Shareholder)
        WHERE s1 < s2
        RETURN s1.name AS shareholder_a,
               s2.name AS shareholder_b,
               count(DISTINCT c) AS shared_companies
        ORDER BY shared_companies DESC
        LIMIT 20
        """,
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    ### Most Connected Co-investors

    How many *different* partners does each shareholder have?
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (s1:Shareholder)-[:HOLDS_SHARES_IN]->(c:Company {status:'REGISTERED'} )<-[:HOLDS_SHARES_IN]-(s2:Shareholder)
        WHERE s1 <> s2
        WITH s1, count(DISTINCT s2) AS co_investors
        RETURN s1.name AS shareholder,
               co_investors
        ORDER BY co_investors DESC
        LIMIT 20
        """,
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    The top connectors are Venture Capital and Trustee firms that co-invest with hundreds of different individuals.

    ## Tight Syndicates: Shareholder Triangles

    A triangle exists when every pair of three shareholders co-invests in
    ≥5 companies together. These are the tightest business relationships
    — property development syndicates, VC co-investors, family groups.
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    We filter out trustee/nominee/custodian names to surface real syndicates.
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (s1:Shareholder)-[:HOLDS_SHARES_IN]->(c:Company)<-[:HOLDS_SHARES_IN]-(s2:Shareholder)
        WHERE elementId(s1) < elementId(s2)
          AND NOT toLower(s1.name) CONTAINS 'trustee'
          AND NOT toLower(s2.name) CONTAINS 'trustee'
          AND NOT toLower(s1.name) CONTAINS 'nominee'
          AND NOT toLower(s2.name) CONTAINS 'nominee'
          AND NOT toLower(s1.name) CONTAINS 'custodian'
          AND NOT toLower(s2.name) CONTAINS 'custodian'
        WITH s1, s2, count(DISTINCT c) AS w
        WHERE w >= 10
        MATCH (s1)-[:HOLDS_SHARES_IN]->(c2:Company)<-[:HOLDS_SHARES_IN]-(s3:Shareholder)
        WHERE elementId(s2) < elementId(s3) AND s3 <> s1
          AND NOT toLower(s3.name) CONTAINS 'trustee'
          AND NOT toLower(s3.name) CONTAINS 'nominee'
          AND NOT toLower(s3.name) CONTAINS 'custodian'
        WITH s1, s2, s3, w
        MATCH (s2)-[:HOLDS_SHARES_IN]->(c3:Company)<-[:HOLDS_SHARES_IN]-(s3)
        WHERE elementId(s1) < elementId(s3)
        WITH s1, s2, s3, w AS ab, count(DISTINCT c3) AS bc
        WHERE bc >= 10
        MATCH (s1)-[:HOLDS_SHARES_IN]->(c4:Company)<-[:HOLDS_SHARES_IN]-(s3)
        WHERE elementId(s1) < elementId(s3)
        WITH s1, s2, s3, ab, bc, count(DISTINCT c4) AS ac
        WHERE ac >= 10
        RETURN s1.name AS a, s2.name AS b, s3.name AS c,
               ab, bc, ac, ab + bc + ac AS total
        ORDER BY total DESC
        LIMIT 30
        """,
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    Triangles often reveal joint ventures: multiple property investors pooling
    capital across several developments, or angel investors consistently backing
    the same startups alongside each other.

    ## Trustee & Nominee "Black Boxes"

    Some entities hold shares in dozens or hundreds of companies but **never
    share a co-investor**. They're nominee shells — a trustee company that
    provides registered office and directorship services but has no economic
    interest in the companies. We call these **"black box" entities**.
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (s:Shareholder)-[:HOLDS_SHARES_IN]->(c:Company)
        WHERE toLower(s.name) CONTAINS 'trustee'
           OR toLower(s.name) CONTAINS 'custodian'
           OR toLower(s.name) CONTAINS 'nominee'
        RETURN s.name AS trustee,
               count(DISTINCT c) AS companies
        ORDER BY companies DESC
        LIMIT 20
        """,
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    DOG TRUSTEE COMPANY LIMITED** holds shares in **600 companies** and
    > appears in the co-investment graph with zero co-investors at the ≥5
    > threshold — it's a pure nominee. The 4 individuals who act as its
    > directors — Bronwyn Ann HANTZ, David Kevin GRAY, Tara WRATTEN,
    > Brendan Timothy WOOD — each sit on **650–665 companies**, virtually all
    > of them for DOG TRUSTEE.
    >
    > ### The Otorohanga Cluster
    >
    > **1,111 companies** share a single registered address:
    > **18 Maniapoto Street, Otorohanga**. This is the Bailey Ingham Trustees
    > network — a trustee services firm that provides registered office and
    > directorship services.
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Director–Shareholder Overlap

    People who sit on the board *and* hold shares in the same company have
    skin in the game. We match across labels by name.
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (d:Director)-[:DIRECTS]->(c:Company)<-[:HOLDS_SHARES_IN]-(s:Shareholder)
        WHERE d.name = s.name
        RETURN d.name AS person,
               count(DISTINCT c) AS overlap_companies
        ORDER BY overlap_companies DESC
        LIMIT 20
        """,
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    ### The Gap Analysis

    For individuals who are large shareholders but *not* directors, the
    gap between shareholder companies and director companies can signal
    nominee activity. A gap of 50+ means they hold shares in 50+ more
    companies than they direct — passive investment or nominee placement.
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (s:Shareholder)
        WHERE s.is_person = true AND s.company_count >= 10
        OPTIONAL MATCH (d:Director {normalized_name: s.normalized_name})-[:DIRECTS]->(c:Company)
        WITH s.normalized_name AS name,
             s.company_count AS sh,
             count(DISTINCT c) AS dir,
             s.company_count - count(DISTINCT c) AS gap
        WHERE gap >= 5
        RETURN name, sh, dir, gap
        ORDER BY gap DESC
        LIMIT 15
        """,
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    ### Exploring the Gap Leaders

    Melissa CLARK tops the list — but what kind of companies is she
    invested in? Let's look at her portfolio.
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (s:Shareholder {normalized_name: 'Melissa CLARK'})-[:HOLDS_SHARES_IN]->(c:Company)
        OPTIONAL MATCH (c)-[:HAS_INDUSTRY]->(ind:Industry)
        RETURN c.name AS company,
               c.status AS status,
               ind.code AS industry_code,
               ind.description AS industry
        ORDER BY status, company
        LIMIT 30
        """,
    )
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (s:Shareholder {normalized_name: 'Melissa CLARK'})-[:HOLDS_SHARES_IN]->(c:Company)
        OPTIONAL MATCH (c)-[:HAS_INDUSTRY]->(ind:Industry)
        RETURN count(DISTINCT c) AS total_companies,
               count(DISTINCT ind.code) AS distinct_industries,
               count(DISTINCT c.status) AS statuses,
               collect(DISTINCT c.status) AS company_statuses
        """,
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    A gap of 160+ with broad industry exposure across both active and
    removed companies is unusual for a genuine active investor. It's more
    consistent with nominee shareholdings placed across a wide range of
    entities.

    ### Industry Diversification Anomaly

    Some surnames appear with extreme industry diversification — investing
    across almost all ANZSIC divisions simultaneously. Let's quantify this.
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (s:Shareholder)-[:HOLDS_SHARES_IN]->(c:Company)-[:HAS_INDUSTRY]->(ind:Industry)
        WHERE s.is_person = true
          AND s.name CONTAINS ' SINGH'
           OR s.name CONTAINS ' KAUR'
           OR s.name CONTAINS ' WEI'
        WITH s.name AS name,
             count(DISTINCT c) AS companies,
             count(DISTINCT ind.code) AS industries
        RETURN name, companies, industries
        ORDER BY industries DESC
        LIMIT 15
        """,
    )
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        // Total ANZSIC divisions
        MATCH (ind:Industry) RETURN count(DISTINCT ind.code) AS total_divisions
        """,
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    Some individuals appear in **130+ companies** across **17+ different
    industry divisions** — that's almost every sector in the ANZSIC
    classification. A genuine investor typically specialises in 2–5
    related industries. Diversification across 17 divisions is far more
    consistent with nominee shareholdings.

    For comparison, let's look at the overall distribution.
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (s:Shareholder)-[:HOLDS_SHARES_IN]->(c:Company)-[:HAS_INDUSTRY]->(ind:Industry)
        WHERE s.sh_type = 'Shareholder Individual'
        WITH s, count(DISTINCT ind.code) AS industries
        RETURN industries, count(*) AS persons
        ORDER BY industries
        """,
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    Nearly all individuals invest in **1–3 industries**. The tail beyond
    10+ is vanishingly small — and dominated by the Singh, Kaur, and Wei
    names. This concentration makes the anomaly stand out starkly.

    Combined, these patterns suggest nominee/director-for-hire operations
    using common names as facades for broad-based share placements.

    ### Who can introduce you?

    Who can introduce you to a given person within 5 co-investment hops?
    Each hop goes through a shared company — so 1 hop is a direct
    co-investor, 2 hops is someone who co-invests with someone who
    co-invests with them, and so on.
    """)
    return


@app.cell
def _(nh):
    target = "Philip Thomas THOMSON"

    nh.mo_table(
        f"""
        MATCH (target)
        WHERE toLower(target.name) = '{target.lower()}'
        MATCH path = shortestPath(
          (target)-[:HOLDS_SHARES_IN*..10]-(introducer:Shareholder)
        )
        WHERE introducer <> target
        RETURN introducer.name AS introducer,
               toInteger(length(path) / 2) AS degrees_of_separation,
               [n IN nodes(path) WHERE n:Company | n.name][0] AS via_company
        ORDER BY degrees_of_separation
        LIMIT 30
        """,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Up next: **[03: Communities & Influence](http://localhost:2718/?file=03_communities_and_influence.py)**
    — network science on the co-investment graph (centrality, communities,
    embeddings).
    """)
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
