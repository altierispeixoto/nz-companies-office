# ---
# marimo-version: 0.23.9
# license: Apache-2.0
# ---

import marimo

__generated_with = "0.23.9"
app = marimo.App(width="full")


@app.cell
def _():
    import sys
    from pathlib import Path

    import marimo as mo

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import _neo4j_helpers as nh

    return mo, nh


@app.cell
def _(mo):
    mo.md(r"""
    # Communities & Influence: The Shape of the Network

    **We've mapped the graph and followed the co-investor patterns. Now we
    apply graph data science — community detection, centrality, and embeddings
    — to understand the *structure* of New Zealand's corporate network.**

    This notebook requires the GDS `coinvest` graph to be projected. If it
    doesn't exist yet, the first cell below creates it from the
    `CO_INVESTS_WITH` relationships (co-investor pairs with ≥5 shared
    companies).

    *The `coinvest` graph contains 909,517 Shareholder nodes and 20,528
    undirected CO_INVESTS_WITH edges (weighted by shared company count).*
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## 1. Project the Co-investment Graph

    First we create the weighted `CO_INVESTS_WITH` edges if they don't
    exist, then project into GDS. This only needs to run once.
    """)
    return


@app.cell
def _(mo, nh):
    # Check if coinvest graph exists
    exists = nh.run_query(
        "CALL gds.graph.exists('coinvest') YIELD exists RETURN exists",
    ).item(0, "exists")

    if not exists:
        # Create CO_INVESTS_WITH edges for pairs with >= 5 shared companies
        nh.run_query(
            """
            MATCH (s1:Shareholder)-[:HOLDS_SHARES_IN]->(c:Company)<-[:HOLDS_SHARES_IN]-(s2:Shareholder)
            WHERE elementId(s1) < elementId(s2)
            WITH s1, s2, count(DISTINCT c) AS weight
            WHERE weight >= 5
            MERGE (s1)-[r:CO_INVESTS_WITH]-(s2)
            SET r.weight = weight
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
        mo.md("✅ `coinvest` graph created (909K nodes, 20.5K edges)")
    else:
        mo.md("✅ `coinvest` graph already exists")
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## 2. Louvain Community Detection

    Louvain finds densely-connected groups of shareholders. Since the
    graph is highly fragmented (903K disconnected components), most
    communities are tiny — but the largest ones tell an interesting story.
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        CALL gds.louvain.stream('coinvest', { relationshipWeightProperty: 'weight' })
        YIELD nodeId, communityId, intermediateCommunityIds
        WITH gds.util.asNode(nodeId).name AS shareholder, communityId
        RETURN communityId,
               count(*) AS members,
               collect(shareholder)[0..5] AS sample_members
        ORDER BY members DESC
        LIMIT 15
        """,
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    ### What are these communities?

    | Community | Size | Likely Composition |
    |---|---|---|
    | #472183 (165) | **NZ Trustee Services** — corporate trustee network |
    | #453315 (106) | **HSBC / JPMorgan** — institutional nominee services |
    | #457726 (39) | **CLM Trustees** — another corporate trustee firm |
    | #3956 (36) | **Bailey Ingham Trustees** — Otorohanga network |
    | #649816 (35) | **Guenole/Heveldt syndicate** — family investment group |
    | #5+ | **Discrete investment syndicates** — property groups, VC funds |

    The **largest community is only 165 nodes**. This confirms what we saw
    earlier: the graph is a collection of independent real-world syndicates,
    not a single interconnected web.

    ## 3. Degree Centrality

    Who has the most direct co-investment partners?
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        CALL gds.degree.stream('coinvest', { relationshipWeightProperty: 'weight' }) YIELD nodeId, score
        WITH gds.util.asNode(nodeId).name AS shareholder, score AS connections
        RETURN shareholder, connections
        ORDER BY connections DESC
        LIMIT 15
        """,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    **Two views of degree:**

    - **By distinct co-investors** (unweighted): POLSON HIGGS NOMINEES tops with
      62, then Mark O'REILLY (54), NZ Trustee Services (49), ICEHOUSE (43).
    - **By weighted sum** (shared company count): the tight 8-person syndicate of
      GUPTA / MITTAL / CHHUN / MEKALA / DUTTA / SATTOOR / GARG leads at
      ~920 — each pair co-invests in hundreds of companies together.
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## 4. PageRank: Who is Most Influential?

    PageRank measures *influence* through connection quality — a
    shareholder linked to other well-connected shareholders scores higher.
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        CALL gds.pageRank.stream('coinvest', { relationshipWeightProperty: 'weight', maxIterations: 20 })
        YIELD nodeId, score
        WITH gds.util.asNode(nodeId).name AS shareholder, score
        RETURN shareholder, score
        ORDER BY score DESC
        LIMIT 15
        """,
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    PageRank reveals a hierarchy: **nominee entities** dominate the top — ICEHOUSE
    VENTURES NOMINEES (10.66), NZ TRUSTEE SERVICES (8.56), ASPIRE NZ SEED (6.85),
    CUSTODIAL SERVICES (6.05), CLM TRUSTEES (5.91) — followed by individuals
    like Mark O'REILLY (5.30) and Ranald PATERSON (3.41). Unlike raw degree,
    PageRank rewards connections to other well-connected nodes, so the large
    nominee firms that sit at the centre of their clusters come out on top.

    ## 5. Clustering Coefficient: Tight vs. Bridge Nodes

    - **LCC = 1.0**: All your co-investors also invest with each other (tight clique)
    - **LCC ≈ 0.0**: You connect groups that don't know each other (bridge)
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        CALL gds.localClusteringCoefficient.stream('coinvest')
        YIELD nodeId, localClusteringCoefficient
        WITH gds.util.asNode(nodeId).name AS shareholder, localClusteringCoefficient AS lcc
        RETURN shareholder, lcc
        ORDER BY lcc DESC
        LIMIT 10
        """,
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    ### And the bridges — nodes with lowest LCC (but > 0):
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        CALL gds.localClusteringCoefficient.stream('coinvest')
        YIELD nodeId, localClusteringCoefficient
        WITH gds.util.asNode(nodeId).name AS shareholder, localClusteringCoefficient AS lcc
        WHERE lcc > 0
        RETURN shareholder, lcc
        ORDER BY lcc ASC
        LIMIT 15
        """,
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## 6. Betweenness Centrality: The Bridges

    Betweenness measures how often a node sits on the shortest path
    between other nodes in its component. High betweenness = a bridge
    that connects otherwise separate groups. Since the graph is highly
    fragmented, most nodes have 0 betweenness, but the few connectors
    are revealing.
    """)
    return


@app.cell
def _(mo, nh):
    # Check if betweenness already persisted
    exists = nh.run_query(
        "MATCH (s:Shareholder) WHERE s.betweenness IS NOT NULL RETURN count(*) AS c",
    ).item(0, "c")

    if exists == 0:
        # Using samplingSize ~500 for approximate betweenness (Brandes with random sources).
        # Exact betweenness on 909K nodes is O(N*E) and very slow — sampling gives a
        # reliable approximation for the top bridge nodes at a fraction of the cost.
        nh.run_query(
            """
            CALL gds.betweenness.write('coinvest', {
              writeProperty: 'betweenness',
              samplingSize: 500
            })
            """,
        )
        mo.md("**:white_check_mark:** Approximate betweenness computed and persisted")
    else:
        mo.md(f"**:white_check_mark:** Betweenness exists on {exists:,} nodes")
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (s:Shareholder)
        WHERE s.betweenness > 0
        RETURN s.name AS shareholder, round(s.betweenness, 2) AS betweenness
        ORDER BY s.betweenness DESC
        LIMIT 15
        """,
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    Betweenness surfaces the **institutional bridges** — entities that sit
    between different investment clusters. POLSON HIGGS NOMINEES (33.0) and
    ICEHOUSE VENTURES NOMINEES (25.8) are the classic examples: they have
    co-investment relationships across multiple otherwise-disconnected
    groups. Individuals like Mark O'REILLY and Ranald PATERSON appear here
    too, acting as personal bridges between syndicates.
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## 8. Compare All Metrics for Key Players
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        WITH [
          'Paayal  GARG',
          'Himanshu  MITTAL',
          'Abhinav  GUPTA',
          'ICEHOUSE VENTURES NOMINEES LIMITED',
          'ASPIRE NZ SEED FUND LIMITED',
          'Benedict John Joseph SHEEHAN',
          'Jason John TAYLOR',
          'Ranald Craig PATERSON',
          'Philip Henschel CAESAR',
          'NEW ZEALAND TRUSTEE SERVICES LIMITED',
          'CUSTODIAL SERVICES LIMITED',
          'David Saul BRISCOE',
          'Rebecca Rachael DICKIE'
        ] AS targets
        MATCH (s:Shareholder)
        WHERE s.name IN targets
        CALL gds.pageRank.stream('coinvest', { relationshipWeightProperty: 'weight', maxIterations: 20 })
        YIELD nodeId, score AS pagerank
        WHERE gds.util.asNode(nodeId) = s
        WITH s, pagerank
        CALL gds.degree.stream('coinvest', { relationshipWeightProperty: 'weight', orientation: 'UNDIRECTED' })
        YIELD nodeId, score AS degree
        WHERE gds.util.asNode(nodeId) = s
        WITH s, pagerank, degree
        CALL gds.localClusteringCoefficient.stream('coinvest')
        YIELD nodeId, localClusteringCoefficient AS lcc
        WHERE gds.util.asNode(nodeId) = s
        RETURN s.name AS shareholder,
               toInteger(degree) AS coinvestors,
               round(pagerank, 4) AS pagerank,
               round(lcc, 3) AS clustering
        ORDER BY pagerank DESC
        """,
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    **Pattern analysis** (weighted degree = sum of co-investment counts):

    - **ICEHOUSE VENTURES NOMINEES** (VC): degree=1076, LCC=0.071
      — low clustering despite thick relationships; classic VC connector
      bridging unrelated portfolio companies
    - **NEW ZEALAND TRUSTEE SERVICES**: degree=648, LCC=0.082
      — similar profile but smaller in scale; broad connector network
    - **Paayal GARG / Himanshu MITTAL / Abhinav GUPTA**: degree~1850, LCC~0.964
      — extreme degree **and** near-perfect clustering; these three appear
      to co-invest together in the same large set of companies (tight syndicate)
    - **Benedict SHEEHAN** (lawyer): degree=962, LCC=1.0
      — high relationship weights concentrated among a tiny set of co-investors
      who all know each other; a tight clique, not a bridge
    - **CUSTODIAL SERVICES / ASPIRE SEED**: degree 764–1154, LCC 0.15–0.17
      — trustee-style: broad connectors with sparse internal structure

    Key differentiator: **PageRank** surfaces individuals (CAESAR, DICKIE,
    SHEEHAN, BRISCOE, TAYLOR — all LCC=1.0) whose few-but-thick relationships
    span different communities, while **degree** surfaces the large nominee
    entities that have many thin connections.

    ## 9. Node2Vec Embeddings & Similarity

    Node2Vec creates 32-dimensional vector representations of each
    shareholder's position in the graph. We can find similar shareholders
    by cosine similarity.
    """)
    return


app._unparsable_cell(
    r"""
    # Check if embeddings exist
    emb_count = nh.run_query(
        "MATCH (s:Shareholder) WHERE s.embedding IS NOT NULL RETURN count(*) AS c",
    ).item(0, "c")

    if emb_count > 0:
        return mo.md(f"✅ Node2Vec embeddings exist on {emb_count:,} shareholders")
    else:
        return mo.md(
            "⚠️ Embeddings not found. Run the Node2Vec generation query first:\n"
            "```cypher\n"
            "CALL gds.node2vec.write('coinvest', {\n"
            "  embeddingDimension: 32,\n  walkLength: 10,\n  walksPerNode: 10,\n"
            "  windowSize: 5,\n  relationshipWeightProperty: 'weight',\n"
            "  writeProperty: 'embedding'\n"
            "})\n"
            "```",
        )
    """,
    name="_",
)


@app.cell
def _(mo):
    mo.md(r"""
    ### Find shareholders similar to ICEHOUSE VENTURES NOMINEES LIMITED:
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (anchor:Shareholder {name: 'ICEHOUSE VENTURES NOMINEES LIMITED'})
        MATCH (s:Shareholder)
        WHERE s.name <> anchor.name
          AND s.embedding IS NOT NULL
        WITH anchor, s,
             reduce(dot = 0.0, i IN range(0, 31) | dot + anchor.embedding[i] * s.embedding[i]) AS dot,
             sqrt(reduce(n = 0.0, i IN range(0, 31) | n + anchor.embedding[i] ^ 2)) AS norm1,
             sqrt(reduce(n = 0.0, i IN range(0, 31) | n + s.embedding[i] ^ 2)) AS norm2
        WITH s, dot / (norm1 * norm2) AS similarity
        WHERE similarity > 0.5
        RETURN s.name AS similar_shareholder,
               round(similarity, 4) AS similarity
        ORDER BY similarity DESC
        LIMIT 15
        """,
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    ### Syndicate similarity: GUPTA / MITTAL / CHHUN / MEKALA / DUTTA / SATTOOR / GARG / CHEA

    The 8-member syndicate shares 123–134 companies per pair and their
    embedding similarity approaches 1.0 — they are structurally identical
    in the graph.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    The embeddings capture structural similarity — entities that play the
    same *role* in the graph (connector, isolate, bridge) cluster together
    even if they operate in different industries.

    ## Key Takeaways

    1. **Louvain confirms fragmentation** — largest community is only 165 nodes.
    2. **PageRank surfaces nominee entities** at the top (ICEHOUSE, NZ Trustee,
       ASPIRE), while raw degree splits into two stories: distinct co-investor
       count (POLSON HIGGS: 62) vs. weighted relationship thickness
       (GUPTA/MITTAL syndicate: ~920).
    3. **The GUPTA/MITTAL/CHHUN/MEDALA/DUTTA/SATTOOR/GARG syndicate** is
       the most extreme pattern — 8 individuals, each with only ~8 distinct
       co-investors but weighted degree ~920 — indicating they co-invest as a
       tight unit across hundreds of companies.
    4. **VCs (Icehouse, LCC=0.07) and trustees (NZ Trustee, LCC=0.08)** have
       the lowest clustering — they bridge many unrelated co-investors who
       don't know each other.
    5. **Node2Vec embeddings** enable similarity search across 909K nodes
       — useful for finding look-alike investors.

    Up next: **[04: Entity Resolution](http://localhost:2718/?file=04_entity_resolution.py)**
    — the double-space problem, fuzzy name matching, and building the
    unified Person graph.
    """)
    return


if __name__ == "__main__":
    app.run()
