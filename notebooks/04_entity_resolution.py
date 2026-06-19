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


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Entity Resolution: One Person, Many Names

    **The NZ Companies Register is a record of *entities* — legal persons
    — not natural persons. An individual can appear as both a shareholder
    and a director, sometimes under slightly different names. The
    Shareholder CSV uses double spaces ("Harpreet  KAUR") while the
    Director CSV uses single spaces ("Harpreet KAUR"). Deciding whether
    two records refer to the same human is the central challenge.**

    We approach it in three stages:

    1. **Exact matching** — normalize whitespace and match directly
    2. **Fuzzy matching** — trigram Jaccard similarity on the name-key
       pre-filter
    3. **Verification** — do the matched entities share at least one
       company? If yes, they're almost certainly the same person.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## The Double-Space Problem

    The bulk CSV export has a quirk: shareholder names contain double spaces
    between first and last names ("Gurpreet  SINGH"), but director names use
    standard single spaces ("Gurpreet SINGH"). Before we can match, we
    collapse all whitespace to a single space.
    """)
    return


@app.cell
def _(mo, nh):
    # Check if entity resolution has been run
    exact_matches = nh.run_query(
        """
        MATCH (s:Shareholder)
        WHERE EXISTS { MATCH (d:Director) WHERE d.normalized_name = s.normalized_name }
        RETURN count(*) AS c
        """,
    ).item(0, "c")

    print(f"{exact_matches}")

    if exact_matches > 0:
        mo.md(
            f"✅ Entity resolution has been run. Found **{exact_matches:,}** Shareholder–Director exact name matches.",
        )
    else:
        mo.md(
            "⚠️ Entity resolution hasn't been run yet. The following cell will execute the setup queries.",
        )
    return


@app.cell
def _(mo, nh):
    # Check setup
    has_normalized = nh.run_query(
        "MATCH (s:Shareholder) WHERE s.normalized_name IS NOT NULL RETURN count(*) AS c LIMIT 1",
    ).item(0, "c")

    if has_normalized == 0:
        # NOTE: Must be two passes because SET evaluates all RHS against the
        # pre-SET state — a single SET cannot self-reference a freshly-set property.
        nh.run_query(
            """
            MATCH (s:Shareholder)
            SET s.normalized_name = trim(apoc.text.replace(s.name, '\\\\s+', ' '))
            """,
        )
        nh.run_query(
            """
            MATCH (d:Director)
            SET d.normalized_name = trim(apoc.text.replace(d.name, '\\\\s+', ' '))
            """,
        )
        nh.run_query(
            """
            MATCH (s:Shareholder)
            SET s.person_id = s.normalized_name,
                s.is_person = CASE WHEN s.normalized_name =~ '.*[a-z].*' THEN true ELSE false END
            """,
        )
        nh.run_query(
            """
            MATCH (d:Director)
            SET d.person_id = d.normalized_name,
                d.is_person = CASE WHEN d.normalized_name =~ '.*[a-z].*' THEN true ELSE false END
            """,
        )
        nh.run_query("CREATE INDEX IF NOT EXISTS FOR (s:Shareholder) ON (s.normalized_name)")
        nh.run_query("CREATE INDEX IF NOT EXISTS FOR (d:Director) ON (d.normalized_name)")
        # name_key = firstWord + lastWord (handles middle-name variants)
        nh.run_query(
            """
            MATCH (s:Shareholder)
            SET s.name_key = toUpper(split(s.normalized_name, ' ')[0])
                            + toUpper(split(s.normalized_name, ' ')[-1])
            """,
        )
        nh.run_query(
            """
            MATCH (d:Director)
            SET d.name_key = toUpper(split(d.normalized_name, ' ')[0])
                            + toUpper(split(d.normalized_name, ' ')[-1])
            """,
        )
        nh.run_query("CREATE INDEX IF NOT EXISTS FOR (s:Shareholder) ON (s.name_key)")
        nh.run_query("CREATE INDEX IF NOT EXISTS FOR (d:Director) ON (d.name_key)")
        mo.md("✅ Setup complete")
    else:
        mo.md("✅ Setup already complete")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Exact Name Matching Results

    After normalizing whitespace, how many people appear in **both** the
    Shareholder *and* Director datasets?
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (s:Shareholder {is_person: true})
        WITH count(DISTINCT s.person_id) AS unique_sh_persons
        MATCH (d:Director {is_person: true})
        WITH unique_sh_persons, count(DISTINCT d.person_id) AS unique_dir_persons
        MATCH (s:Shareholder {is_person: true})
        WHERE EXISTS { MATCH (d:Director) WHERE d.normalized_name = s.normalized_name }
        WITH unique_sh_persons, unique_dir_persons, count(DISTINCT s) AS with_both
        MATCH (d:Director {is_person: true})
        WHERE NOT EXISTS { MATCH (s:Shareholder) WHERE s.normalized_name = d.normalized_name }
        RETURN unique_sh_persons AS unique_shareholders,
               unique_dir_persons AS unique_directors,
               with_both AS matched_persons,
               count(DISTINCT d) AS directors_only
        """,
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    **Over 600,000 names match exactly** — remarkable. There are also ~75K
    directors who don't appear as shareholders (they run companies but
    don't own shares in them).

    But 600K exact matches hides a problem: many common names match
    incorrectly. "John SMITH" as a shareholder is almost certainly a
    *different* John SMITH than "John SMITH" as a director. We need
    additional signals — company overlap, address overlap — to
    disambiguate.

    ## Trigram Fuzzy Matching

    For names that *don't* match exactly but are likely the same person
    (e.g., "Melissa CLARK" vs "Melissa Alice CLARK"), we use trigram
    similarity:

    1. Pad the name: `  melissa clark `
    2. Extract all 3-character sliding windows: `  m`, ` me`, `mel`,
       `eli`, `lis`, `iss`, etc.
    3. Jaccard similarity = |intersection| / |union| between the
       trigram sets
    4. Thresholds: ≥0.65 = high, ≥0.55 = medium, ≥0.5 = low

    We pre-filter with `name_key` (first letter of first name + last name)
    to avoid scanning all 676K shareholders.
    """)
    return


@app.cell
def _(mo, nh):
    # Check if trigrams have been computed
    has_trigrams = nh.run_query(
        "MATCH (s:Shareholder) WHERE s.trigrams IS NOT NULL RETURN count(*) AS c LIMIT 1",
    ).item(0, "c")

    if has_trigrams == 0:
        # Compute trigrams
        nh.run_query(
            """
            MATCH (n)
            WHERE (n:Shareholder OR n:Director) AND n.normalized_name IS NOT NULL
            WITH n, toLower(n.normalized_name) AS clean
            WITH n, '  ' + clean + ' ' AS padded
            SET n.trigrams = [i IN range(0, size(padded) - 3) | substring(padded, i, 3)]
            """,
        )
        # trigram matching for Shareholder -> Director
        nh.run_query(
            """
            MATCH (s:Shareholder)
            WHERE NOT EXISTS { MATCH (d:Director) WHERE d.normalized_name = s.normalized_name }
              AND s.is_person = true AND s.company_count >= 3
              AND s.name_key IS NOT NULL AND s.trigrams IS NOT NULL
            WITH s
            MATCH (d:Director)
            WHERE d.name_key = s.name_key AND d.is_person = true AND d.trigrams IS NOT NULL
            WITH s, d,
                 size([x IN s.trigrams WHERE x IN d.trigrams]) * 1.0
                   / (size(s.trigrams) + size(d.trigrams)
                      - size([x IN s.trigrams WHERE x IN d.trigrams])) AS jaccard
            WHERE jaccard >= 0.5
            WITH s, d.normalized_name AS match_name, jaccard
            ORDER BY jaccard DESC
            WITH s, collect(match_name)[0] AS best_match, max(jaccard) AS best_score
            SET s.trigram_match = best_match,
                s.trigram_score = best_score,
                s.match_confidence = CASE
                  WHEN best_score >= 0.65 THEN 'high'
                  WHEN best_score >= 0.55 THEN 'medium'
                  WHEN best_score >= 0.5 THEN 'low'
                END
            """,
        )
        # trigram matching for Director -> Shareholder
        nh.run_query(
            """
            MATCH (d:Director)
            WHERE NOT EXISTS { MATCH (s:Shareholder) WHERE s.normalized_name = d.normalized_name }
              AND d.is_person = true AND d.name_key IS NOT NULL AND d.trigrams IS NOT NULL
            WITH d
            MATCH (s:Shareholder)
            WHERE s.name_key = d.name_key AND s.is_person = true AND s.trigrams IS NOT NULL
            WITH d, s,
                 size([x IN d.trigrams WHERE x IN s.trigrams]) * 1.0
                   / (size(d.trigrams) + size(s.trigrams)
                      - size([x IN d.trigrams WHERE x IN s.trigrams])) AS jaccard
            WHERE jaccard >= 0.55
            WITH d, s.normalized_name AS match_name, jaccard
            ORDER BY jaccard DESC
            WITH d, collect(match_name)[0] AS best_match, max(jaccard) AS best_score
            SET d.trigram_match = best_match,
                d.trigram_score = best_score,
                d.match_confidence = CASE
                  WHEN best_score >= 0.65 THEN 'high'
                  WHEN best_score >= 0.55 THEN 'medium'
                END
            """,
        )
        mo.md("✅ Trigrams computed and fuzzy matching complete")
    else:
        mo.md("✅ Trigrams already computed")
    return


@app.cell
def _(mo):
    mo.md(r"""
    ### Fuzzy match candidates

    How many unmatched shareholders have a name_key collision with a director?
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (s:Shareholder)
        WHERE NOT EXISTS { MATCH (d:Director) WHERE d.normalized_name = s.normalized_name }
          AND EXISTS { MATCH (d:Director) WHERE d.name_key = s.name_key }
          AND s.is_person = true AND s.company_count >= 5
        RETURN count(*) AS fuzzy_candidates
        """,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Creating the Unified Person Graph

    For each trigram match, we create a `Person` node (canonical identity)
    and a `SAME_AS` relationship from the variant name to the canonical
    person. This gives us a unified view of every human in the dataset.
    """)
    return


@app.cell
def _(mo, nh):
    # Check if Person nodes already exist
    person_count = nh.run_query("MATCH (p:Person) RETURN count(*) AS c").item(0, "c")

    if person_count > 0:
        mo.md(f"✅ **{person_count:,}** Person nodes already exist")
    else:
        nh.run_query(
            """
            MATCH (s:Shareholder) WHERE s.trigram_match IS NOT NULL
            WITH DISTINCT s.trigram_match AS canonical
            MERGE (p:Person {person_id: canonical})
            """,
        )
        nh.run_query(
            """
            MATCH (d:Director) WHERE d.trigram_match IS NOT NULL
              AND NOT EXISTS { MATCH (p:Person {person_id: d.trigram_match}) }
            WITH DISTINCT d.trigram_match AS canonical
            MERGE (p:Person {person_id: canonical})
            """,
        )
        nh.run_query("CREATE INDEX person_id IF NOT EXISTS FOR (p:Person) ON (p.person_id)")
        nh.run_query(
            """
            MATCH (s:Shareholder) WHERE s.trigram_match IS NOT NULL
            MATCH (p:Person {person_id: s.trigram_match})
            CREATE (s)-[:SAME_AS {score: s.trigram_score, confidence: s.match_confidence}]->(p)
            """,
        )
        nh.run_query(
            """
            MATCH (d:Director) WHERE d.trigram_match IS NOT NULL
              AND NOT EXISTS { MATCH (d)-[:SAME_AS]->(:Person) }
            MATCH (p:Person {person_id: d.trigram_match})
            CREATE (d)-[:SAME_AS {score: d.trigram_score, confidence: d.match_confidence}]->(p)
            """,
        )
        person_count = nh.run_query("MATCH (p:Person) RETURN count(*) AS c").item(0, "c")
        mo.md(f"✅ Created **{person_count:,}** Person nodes")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Verification by Company Overlap

    The critical test: do trigram-matched Shareholder–Director pairs
    share at least one company? If they do, the match is almost certainly
    correct (they're an investor-director in the same business). If not,
    it could be a false positive (different people with similar names).
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (s:Shareholder)-[r:SAME_AS]->(p:Person)
        WHERE s.trigram_score >= 0.55
        MATCH (d:Director {person_id: p.person_id})
        OPTIONAL MATCH (s)-[:HOLDS_SHARES_IN]->(c:Company)<-[:DIRECTS]-(d)
        WITH r, count(DISTINCT c) AS overlap
        SET r.company_overlap = overlap,
            r.verified = CASE WHEN overlap >= 1 THEN true ELSE false END
        RETURN r.verified AS verified,
               round(avg(r.score), 3) AS avg_trigram_score,
               count(*) AS count
        ORDER BY verified
        """,
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    ### Understanding the numbers

    | Result | Count | Meaning |
    |---|---|---|
    | **Verified** (≥1 shared company) |  33,918 | Confirmed same person — they invest in and direct at least one common company |
    | **Not verified** (0 shared companies) | 30,025 | False positives — different people with similar names |
    | **Strong matches** (≥3 shared companies) | 291 | Almost certainly same person |

    A **33% verification rate is reasonable** for trigram-only matching.
    The 30K false positives are overwhelmingly common names (Singh, Kaur,
    Patel, Smith) where different people happen to have similar names.
    Adding address overlap as a second verification signal could improve
    this.

    ### People with the most verified name variants
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (s:Shareholder)-[r:SAME_AS {verified: true}]->(p:Person)
        WITH p, collect(DISTINCT s.normalized_name) AS variants
        MATCH (d:Director {person_id: p.person_id})
        WITH p.person_id AS canonical, variants + [p.person_id] AS all_names
        UNWIND all_names AS name
        WITH canonical, collect(DISTINCT name) AS unique_names
        RETURN canonical, size(unique_names) AS verified_variants, unique_names
        ORDER BY verified_variants DESC
        LIMIT 15
        """,
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Key Takeaways

    1. **604,671 exact matches** — names that appear in both Shareholder and
       Director datasets after normalizing whitespace.
    2. **105,080 Person nodes created** from trigram fuzzy matching, with
       **117,499 SAME_AS relationships**.
    3. **33,918 verified by company overlap** — proven same person because
       they invest and direct in at least one shared company.
    4. **30,025 false positives** — common names where the trigram match was
       coincidental (different people).
    5. **291 strong matches** (≥3 shared companies) — almost certainly correct.
    6. **Address overlap** would further reduce false positives.

    Up next: **[05: Predicting Investor Types](http://localhost:2718/?file=05_predicting_investor_types.py)**
    — using graph embeddings and features to classify investors as VC,
    property, trustee, or accounting.
    """)
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
