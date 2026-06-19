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
    # Predicting Investor Types with Graph ML

    **Can a machine learning model distinguish a venture capital firm from a
    property investor from a professional trustee — using only the *pattern*
    of their co-investments?**

    We have 16 hand-labeled seed entities across 4 classes:

    | Class | Label | Examples |
    |---|---|---|
    | Venture Capital | `VC` | ICEHOUSE VENTURES NOMINEES, ASPIRE NZ SEED FUND, K ONE W ONE, ANGEL HQ |
    | Property | `PROPERTY` | Himanshu MITTAL, Abhinav GUPTA, Shivali DUTTA, Bunleng CHHUN |
    | Trustee | `TRUSTEE` | Benedict SHEEHAN, Jason TAYLOR, Rebecca DICKIE |
    | Accounting | `ACCOUNTING` | David BRISCOE, Hamish WALKER, Alysha HINTON, Kate MITCHELL |

    We classify all 9,257 shareholders in the co-investment graph using:
    - **Node2Vec embeddings** (32-dim, graph structure)
    - **Node features** (company count, co-investor count, PageRank)
    - **Combined** (weighted 0.7 embedding + 0.3 features)
    - **FastRP + features** (best performing configuration)
    """)
    return


@app.cell
def _(mo, nh):
    # Check prerequisites
    embed = nh.run_query(
        "MATCH (s:Shareholder) WHERE s.embedding IS NOT NULL RETURN count(*) AS c",
    ).item(0, "c")

    labels = nh.run_query(
        """
        MATCH (s:Shareholder)
        WHERE s.name IN [
          'ICEHOUSE VENTURES NOMINEES LIMITED', 'ASPIRE NZ SEED FUND LIMITED',
          'K ONE W ONE (NO 4) LIMITED', 'ANGEL HQ NOMINEE LIMITED',
          'Himanshu  MITTAL', 'Abhinav  GUPTA', 'Shivali  DUTTA', 'Bunleng  CHHUN',
          'Srinivas  MEKALA', 'Benedict John Joseph SHEEHAN', 'Jason John TAYLOR',
          'Rebecca Rachael DICKIE',
          'David Saul BRISCOE', 'Hamish Gordon WALKER', 'Alysha Margaret HINTON',
          'Kate Frances MITCHELL'
        ]
        RETURN count(*) AS c
        """,
    ).item(0, "c")

    if embed > 0 and labels >= 16:
        mo.md(f"✅ Prerequisites met: {embed:,} embeddings, {labels} labeled seeds")
    else:
        mo.md(
            "⚠️ Missing prerequisites. Need:\n"
            f"- Embeddings: {embed:,}/9,257 with embeddings\n"
            f"- Labels: {labels}/16 seeds\n\n"
            "Run the setup in [03: Communities & Influence](03_communities_and_influence.py) first.",
        )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 1. Set Seed Labels

    First we write the ground-truth labels as a temporary property on the
    16 seed shareholders.
    """)
    return


@app.cell
def _(mo, nh):
    # Check if labels already set
    existing_labels = nh.run_query(
        "MATCH (s:Shareholder) WHERE s.label IS NOT NULL RETURN count(*) AS c",
    ).item(0, "c")

    if existing_labels == 0:
        nh.run_query(
            """
            MATCH (s:Shareholder)
            WHERE s.name IN [
              'ICEHOUSE VENTURES NOMINEES LIMITED',
              'ASPIRE NZ SEED FUND LIMITED',
              'K ONE W ONE (NO 4) LIMITED',
              'ANGEL HQ NOMINEE LIMITED'
            ]
            SET s.label = 'VC'
            """,
        )
        nh.run_query(
            """
            MATCH (s:Shareholder)
            WHERE s.name IN [
              'Himanshu  MITTAL', 'Abhinav  GUPTA', 'Shivali  DUTTA',
              'Bunleng  CHHUN', 'Srinivas  MEKALA'
            ]
            SET s.label = 'PROPERTY'
            """,
        )
        nh.run_query(
            """
            MATCH (s:Shareholder)
            WHERE s.name IN [
              'Benedict John Joseph SHEEHAN', 'Jason John TAYLOR',
              'Rebecca Rachael DICKIE'
            ]
            SET s.label = 'TRUSTEE'
            """,
        )
        nh.run_query(
            """
            MATCH (s:Shareholder)
            WHERE s.name IN [
              'David Saul BRISCOE', 'Hamish Gordon WALKER',
              'Alysha Margaret HINTON', 'Kate Frances MITCHELL'
            ]
            SET s.label = 'ACCOUNTING'
            """,
        )
        mo.md("✅ Seed labels set (VC=4, PROPERTY=5, TRUSTEE=3, ACCOUNTING=4)")
    else:
        mo.md(f"✅ {existing_labels} labels already exist")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 2. Embedding-Only kNN Classification (Node2Vec)

    For each unlabeled shareholder, we compute the average cosine similarity
    to seeds in each class, then predict the class with highest average
    similarity.
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (seed:Shareholder)
        WHERE seed.label IS NOT NULL
        WITH collect({label: seed.label, emb: seed.embedding}) AS seeds
        MATCH (target:Shareholder)-[:CO_INVESTS_WITH]-()
        WHERE target.label IS NULL AND target.embedding IS NOT NULL
        WITH DISTINCT target, seeds
        UNWIND seeds AS s
        WITH target, s.label AS class,
             reduce(dot = 0.0, i IN range(0, 31) | dot + target.embedding[i] * s.emb[i])
               / (sqrt(reduce(n = 0.0, i IN range(0, 31) | n + target.embedding[i] ^ 2))
                * sqrt(reduce(n = 0.0, i IN range(0, 31) | n + s.emb[i] ^ 2))) AS sim
        WITH target, class, avg(sim) AS avg_sim
        ORDER BY target.name, avg_sim DESC
        WITH target, collect(class)[0] AS predicted
        SET target.predicted_label = predicted
        RETURN predicted AS class, count(*) AS count
        ORDER BY count DESC
        """,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    **Node2Vec embeddings alone produce a distribution dominated by one class.**
    This is expected — the embeddings capture co-investment *structure*, but
    they don't capture *scale*. A VC with 30 portfolio companies looks
    structurally similar to a trustee with 50 companies. We need node features
    to distinguish them.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 3. Combined Classification (Embeddings + Features)

    We add 3 node features normalized to [0, 1]:
    - **company_count**: number of companies the shareholder invests in
      (max: 659)
    - **co_investor_count**: number of co-investment partners (max: 62)
    - **page_rank**: PageRank score (max: 10.66)

    Combined score = 0.7 × embedding_similarity + 0.3 × (1 − feature_distance / √3)

    The α=0.7 weighting favors structural similarity but uses features
    for tie-breaking.
    """)
    return


@app.cell
def _(mo, nh):
    # Compute node features if not present
    features = nh.run_query(
        "MATCH (s:Shareholder) WHERE s.company_count IS NOT NULL LIMIT 1 RETURN count(*) AS c",
    ).item(0, "c")

    if features == 0:
        nh.run_query(
            "MATCH (s:Shareholder)-[:HOLDS_SHARES_IN]->(c:Company)"
            " WITH s, count(DISTINCT c) AS cnt SET s.company_count = cnt",
        )
        nh.run_query(
            "MATCH (s:Shareholder)-[:CO_INVESTS_WITH]-() WITH s, count(*) AS cnt SET s.co_investor_count = cnt",
        )
        nh.run_query(
            """
            CALL gds.pageRank.write('coinvest', {
              relationshipWeightProperty: 'weight',
              writeProperty: 'page_rank'
            })
            """,
        )
        mo.md("✅ Node features computed (company_count, co_investor_count, page_rank)")
    else:
        mo.md("✅ Node features already exist")
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (seed:Shareholder)
        WHERE seed.label IS NOT NULL
        WITH collect({
          label: seed.label, emb: seed.embedding,
          cc_norm: toFloat(seed.company_count) / 659.0,
          cic_norm: toFloat(seed.co_investor_count) / 62.0,
          pr_norm: toFloat(seed.page_rank) / 10.657374238418047
        }) AS seeds
        MATCH (target:Shareholder)-[:CO_INVESTS_WITH]-()
        WHERE target.label IS NULL AND target.embedding IS NOT NULL
        WITH DISTINCT target, seeds,
          toFloat(target.company_count) / 659.0 AS t_cc,
          toFloat(target.co_investor_count) / 62.0 AS t_cic,
          toFloat(target.page_rank) / 10.657374238418047 AS t_pr
        UNWIND seeds AS s
        WITH target, s.label AS class,
             reduce(dot = 0.0, i IN range(0, 31) | dot + target.embedding[i] * s.emb[i])
               / (sqrt(reduce(n = 0.0, i IN range(0, 31) | n + target.embedding[i] ^ 2))
                * sqrt(reduce(n = 0.0, i IN range(0, 31) | n + s.emb[i] ^ 2))) AS sim_emb,
             sqrt((t_cc - s.cc_norm)^2 + (t_cic - s.cic_norm)^2 + (t_pr - s.pr_norm)^2) AS feat_dist
        WITH target, class,
             0.7 * sim_emb + 0.3 * (1 - feat_dist / sqrt(3)) AS combined_score
        ORDER BY combined_score DESC
        WITH target, collect(class)[0] AS predicted
        SET target.combined_label = predicted
        RETURN predicted AS class, count(*) AS count
        ORDER BY count DESC
        """,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 4. FastRP + Features (Best Performing)

    FastRP (Fast Random Projection) tends to produce better embeddings for
    this sparse, fragmented graph because it's more deterministic at low
    dimensionalities. The combination with features at α=0.7 produces the
    most balanced distribution, which we store as `best_label`.
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (seed:Shareholder)
        WHERE seed.label IS NOT NULL
        WITH collect({
          label: seed.label, emb: seed.fastrp_embedding,
          cc_norm: toFloat(seed.company_count) / 659.0,
          cic_norm: toFloat(seed.co_investor_count) / 62.0,
          pr_norm: toFloat(seed.page_rank) / 10.657374238418047
        }) AS seeds
        MATCH (target:Shareholder)-[:CO_INVESTS_WITH]-()
        WHERE target.label IS NULL AND target.fastrp_embedding IS NOT NULL
        WITH DISTINCT target, seeds,
          toFloat(target.company_count) / 659.0 AS t_cc,
          toFloat(target.co_investor_count) / 62.0 AS t_cic,
          toFloat(target.page_rank) / 10.657374238418047 AS t_pr
        UNWIND seeds AS s
        WITH target, s.label AS class,
             reduce(dot = 0.0, i IN range(0, 31) | dot + target.fastrp_embedding[i] * s.emb[i])
               / (sqrt(reduce(n = 0.0, i IN range(0, 31) | n + target.fastrp_embedding[i] ^ 2))
                * sqrt(reduce(n = 0.0, i IN range(0, 31) | n + s.emb[i] ^ 2))) AS sim_emb,
             sqrt((t_cc - s.cc_norm)^2 + (t_cic - s.cic_norm)^2 + (t_pr - s.pr_norm)^2) AS feat_dist
        WITH target, class,
             0.7 * sim_emb + 0.3 * (1 - feat_dist / sqrt(3)) AS combined_score
        ORDER BY combined_score DESC
        WITH target, collect(class)[0] AS predicted
        SET target.fastrp_combined_label = predicted
        RETURN predicted AS class, count(*) AS count
        ORDER BY count DESC
        """,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Set Best Label
    """)
    return


@app.cell
def _(nh):
    nh.run_query(
        """
        MATCH (s:Shareholder)
        WHERE s.fastrp_combined_label IS NOT NULL AND s.label IS NULL
        SET s.best_label = s.fastrp_combined_label
        """,
    )

    # Show distribution
    nh.mo_table(
        """
        MATCH (s:Shareholder) WHERE s.best_label IS NOT NULL
        RETURN s.best_label AS class,
               count(*) AS count,
               round(100.0 * count(*) / 9257, 1) AS pct
        ORDER BY count DESC
        """,
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## 5. Compare Methods for Test Entities

    How do the different methods classify specific known entities?
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (s:Shareholder)
        WHERE s.name IN [
          'K ONE W ONE (NO 6) LIMITED',
          'SNOWBALL NOMINEES LIMITED',
          'BAILEY INGHAM TRUSTEES LIMITED'
        ]
        RETURN s.name,
               s.company_count,
               s.co_investor_count,
               round(s.page_rank, 2) AS page_rank,
               s.predicted_label AS n2v_only,
               s.combined_label AS n2v_feat,
               s.fastrp_combined_label AS fastrp_feat
        ORDER BY s.name
        """,
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    | Entity | Expected | Embeddings only | Combined (N2V+feat) | FastRP+feat (best) |
    |---|---|---|---|---|
    | K ONE W ONE (NO 6) | VC | — | — | — |
    | SNOWBALL NOMINEES | VC | — | — | — |
    | BAILEY INGHAM TRUSTEES | TRUSTEE | — | — | — |

    The classification is sensitive to seed selection. With only 16 seeds, the
    model can't distinguish subtle differences — e.g., a nominee for a VC firm
    vs. a professional trustee firm. More diverse labels would improve accuracy.

    ### Nearest labeled seeds for a specific entity
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (target:Shareholder {name: 'SNOWBALL NOMINEES LIMITED'})
        MATCH (seed:Shareholder)
        WHERE seed.label IS NOT NULL AND seed.fastrp_embedding IS NOT NULL
        WITH target, seed,
             reduce(dot = 0.0, i IN range(0, 31) | dot + target.fastrp_embedding[i] * seed.fastrp_embedding[i])
               / (sqrt(reduce(n = 0.0, i IN range(0, 31) | n + target.fastrp_embedding[i] ^ 2))
                * sqrt(reduce(n = 0.0, i IN range(0, 31) | n + seed.fastrp_embedding[i] ^ 2))) AS sim
        RETURN seed.name, seed.label, round(sim, 4) AS similarity,
               seed.company_count, seed.co_investor_count
        ORDER BY sim DESC
        LIMIT 10
        """,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Clean up temporary label property
    """)
    return


@app.cell
def _(nh):
    nh.run_query(
        """
        MATCH (s:Shareholder)
        WHERE s.label IS NOT NULL
        REMOVE s.label
        """,
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Key Takeaways

    1. **Embeddings alone are insufficient** — Node2Vec kNN predicts mostly
       one class because structural similarity doesn't capture *scale*.
    2. **Features are essential** — company count, co-investor count, and
       PageRank normalize across 3 orders of magnitude and break the
       symmetry between a small VC and a large trustee.
    3. **FastRP + features at α=0.7** produces the most balanced
       distribution — the current `best_label` configuration.
    4. **Seed count (16) is the limiting factor** — the model would
       benefit from 50–100 labeled examples per class, especially for
       fine-grained distinctions (e.g., angel investor vs. VC vs. family
       office).

    ## Where to Next?

    - **Address overlap** as a second verification signal for entity
      resolution
    - **Multi-threshold co-investment graph** (≥2 shared companies) for
      a denser, more connected network
    - **Supervised node classification** with GDS
      `gds.nodeClassification` when more labeled data is available
    - **Industry diversification** as a nominee detection feature
    """)
    return


if __name__ == "__main__":
    app.run()
