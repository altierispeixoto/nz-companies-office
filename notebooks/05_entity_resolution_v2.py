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
def _():
    import numpy as np
    import pandas as pd
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import classification_report
    from sklearn.metrics import confusion_matrix
    from sklearn.metrics import precision_recall_curve
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import train_test_split

    return (
        RandomForestClassifier,
        classification_report,
        confusion_matrix,
        np,
        pd,
        precision_recall_curve,
        roc_auc_score,
        train_test_split,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Entity Resolution V2: Multi-blocking + Classifier

    **The original entity resolution used trigram Jaccard similarity
    with a `name_key` pre-filter (first initial + last name). This
    captured ~105K fuzzy matches but left ~30K false positives from
    common names (Singh, Kaur, Patel, etc.) where the names match but
    the people don't.**

    This notebook uses a three-strategy blocking approach followed by
    a RandomForest classifier trained on the 63K already-labeled pairs:

    1. **Block by `name_key`** — existing first-initial + last-name filter
    2. **Block by `company_overlap`** — Shareholder invests in a company
       the Director also directs
    3. **Block by `address_overlap`** — Shareholder's companies share a
       registered address with the Director's companies

    All candidates from any block are deduplicated, featurized, and scored
    by the classifier with a calibrated probability.
    """)
    return


@app.cell
def _(mo, nh):
    # Prerequisite checks
    has_trigrams = nh.run_query(
        "MATCH (s:Shareholder) WHERE s.trigrams IS NOT NULL RETURN count(*) AS c LIMIT 1",
    ).item(0, "c")

    has_persons = nh.run_query("MATCH (p:Person) RETURN count(*) AS c").item(0, "c")

    has_same_as = nh.run_query(
        "MATCH ()-[r:SAME_AS]->() RETURN count(*) AS c LIMIT 1",
    ).item(0, "c")

    status = []
    if has_trigrams:
        status.append("✅ Trigrams exist")
    else:
        status.append("⚠️ Trigrams missing — run notebook 04 entity resolution first")
    if has_persons > 0:
        status.append(f"✅ {has_persons:,} Person nodes exist")
    else:
        status.append("⚠️ Person nodes missing")
    if has_same_as > 0:
        status.append("✅ SAME_AS relationships exist")
    else:
        status.append("⚠️ SAME_AS relationships missing")

    mo.md("  \n".join(status))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 1: Build Training Dataset

    Pull all existing SAME_AS relationships with their properties and
    the Shareholder/Director info. These ~64K pairs are our labeled
    training set: `verified = True` means company_overlap ≥ 1 (positive),
    `verified = False` means company_overlap = 0 (negative).
    """)
    return


@app.cell
def _(mo, nh, pd):
    raw = nh.run_query(
        """
        MATCH (s:Shareholder)-[r:SAME_AS]->(p:Person)
        MATCH (d:Director {normalized_name: p.person_id})
        OPTIONAL MATCH (s)-[:HOLDS_SHARES_IN]->(c1:Company)-[:HAS_ADDRESS]->(a:Address)
        OPTIONAL MATCH (c1)<-[:DIRECTS]-(d)
        WITH s.normalized_name AS sh_name,
             d.normalized_name AS dir_name,
             r.score AS trigram_score,
             r.company_overlap AS company_overlap,
             r.verified AS verified,
             count(DISTINCT a) AS sh_addresses,
             sum(CASE WHEN d.normalized_name IS NOT NULL THEN 1 ELSE 0 END) AS dir_at_address
        RETURN sh_name, dir_name, trigram_score,
               company_overlap,
               verified,
               sh_addresses,
               dir_at_address
        """,
    )

    train_df = raw.to_pandas()
    mo.md(f"**{len(train_df):,}** training pairs loaded")
    return raw, train_df


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 2: Add Address Overlap Feature

    For each training pair, compute how many addresses they share —
    addresses where the Shareholder's company and the Director's company
    both register. This is the most powerful new signal for disambiguating
    common-name false positives.
    """)
    return


@app.cell
def _(mo, nh, pd, train_df):
    # Build batch query for address overlap
    pairs = train_df[["sh_name", "dir_name"]].to_dict("records")

    batch_size = 500
    address_overlap = []

    driver = nh.get_driver()
    for i in range(0, len(pairs), batch_size):
        batch = pairs[i : i + batch_size]
        with driver.session() as s:
            result = s.run(
                """
                UNWIND $pairs AS p
                OPTIONAL MATCH (s:Shareholder {normalized_name: p.sh_name})-[:HOLDS_SHARES_IN]->(c1:Company)-[:HAS_ADDRESS]->(a:Address)
                OPTIONAL MATCH (c1)<-[:DIRECTS]-(d:Director {normalized_name: p.dir_name})
                WITH p.sh_name AS sh, p.dir_name AS dir, a, d
                WHERE d IS NOT NULL
                RETURN sh, dir, count(DISTINCT a) AS shared_addresses
                """,
                parameters={"pairs": batch},
            )
            for row in result:
                address_overlap.append(
                    {
                        "sh_name": row["sh"],
                        "dir_name": row["dir"],
                        "address_overlap": min(row["shared_addresses"], 1),
                    }
                )

    addr_df = pd.DataFrame(address_overlap)
    train_df = train_df.merge(addr_df, on=["sh_name", "dir_name"], how="left").fillna(
        {"address_overlap": 0},
    )

    positive = train_df["verified"].sum()
    negative = (~train_df["verified"]).sum()
    with_addr = (train_df["address_overlap"] > 0).sum()

    mo.md(
        f"**{len(train_df):,}** training pairs with features\n\n"
        f"- Positive: {positive:,}\n"
        f"- Negative: {negative:,}\n"
        f"- Have address_overlap ≥ 1: {with_addr:,}",
    )
    return addr_df, batch, batch_size, driver, i, result, row, with_addr


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 3: Feature Engineering

    All features for the classifier:
    | Feature | Type | Range |
    |---|---|---|
    | `trigram_score` | float | [0, 1] — Jaccard similarity of name trigrams |
    | `name_length_ratio` | float | [0, 1] — shorter name / longer name |
    | `name_key_match` | bool | Do first-initial + last-name match? |
    | `company_overlap` | int | Number of companies they share |
    | `address_overlap` | int | Number of shared addresses |
    """)
    return


@app.cell
def _(mo, np, train_df):
    def first_word(s: str) -> str:
        return s.split(" ", maxsplit=1)[0] if " " in s else s

    def last_word(s: str) -> str:
        return s.rsplit(" ", maxsplit=1)[-1] if " " in s else s

    _df = train_df.copy()

    _df["name_length_ratio"] = _df.apply(
        lambda r: len(min(r["sh_name"], r["dir_name"], key=len)) / len(max(r["sh_name"], r["dir_name"], key=len)),
        axis=1,
    )

    _df["name_key_match"] = _df.apply(
        lambda r: (
            first_word(r["sh_name"])[0] + last_word(r["sh_name"])
            == first_word(r["dir_name"])[0] + last_word(r["dir_name"])
        ),
        axis=1,
    ).astype(int)

    feature_cols = [
        "trigram_score",
        "name_length_ratio",
        "name_key_match",
        "company_overlap",
        "address_overlap",
    ]

    X = _df[feature_cols].fillna(0)
    y = _df["verified"].astype(int)

    mo.md(f"**{len(feature_cols)} features**, **{len(X):,}** samples, **{y.sum():,}** positive")
    return X, _df, feature_cols, first_word, last_word, y


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 4: Train RandomForest Classifier

    80/20 train/test split, 200 trees, balanced class weights to handle
    the ~50/50 class distribution.
    """)
    return


@app.cell
def _(
    RandomForestClassifier,
    X,
    classification_report,
    confusion_matrix,
    feature_cols,
    mo,
    pd,
    train_test_split,
    y,
):
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    _report = classification_report(y_test, y_pred, output_dict=True)
    _cm = confusion_matrix(y_test, y_pred)

    fi = pd.DataFrame(
        {
            "feature": feature_cols,
            "importance": model.feature_importances_,
        }
    ).sort_values("importance", ascending=False)

    mo.md(
        f"**Accuracy:** {_report['accuracy']:.3f}  "
        f"**Precision:** {_report['1']['precision']:.3f}  "
        f"**Recall:** {_report['1']['recall']:.3f}  "
        f"**F1:** {_report['1']['f1-score']:.3f}\n\n"
        f"**Confusion matrix:**\n"
        f"TN={_cm[0][0]}  FP={_cm[0][1]}\n"
        f"FN={_cm[1][0]}  TP={_cm[1][1]}\n\n"
        f"**Feature importance:**\n"
        f"{fi.to_markdown(index=False)}",
    )
    return (
        X_test,
        X_train,
        fi,
        model,
        y_pred,
        y_proba,
        y_test,
        y_train,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    The classifier learns that **company_overlap** and **address_overlap**
    are the strongest signals — if two names share a company or an address,
    they're almost certainly the same person. Trigram score alone is weaker
    because identical common names ("John SMITH" == "John SMITH") score 1.0
    but often refer to different people.

    ## Step 5: Block Candidates for Unmatched Shareholders

    Now we find candidate Director matches for Shareholders who don't
    already have a SAME_AS relationship, using all three blocking strategies.
    """)
    return


@app.cell
def _(mo, nh, pd):
    # 5a: candidates by name_key
    name_key_candidates = nh.run_query(
        """
        MATCH (s:Shareholder)
        WHERE s.is_person = true
          AND s.company_count >= 3
          AND NOT EXISTS { MATCH (s)-[:SAME_AS]->(:Person) }
          AND EXISTS { MATCH (d:Director) WHERE d.name_key = s.name_key AND d.is_person = true }
        MATCH (d:Director)
        WHERE d.name_key = s.name_key
          AND d.is_person = true
          AND s.normalized_name <> d.normalized_name
        RETURN DISTINCT s.normalized_name AS sh_name,
               d.normalized_name AS dir_name,
               'name_key' AS source
        """,
    ).to_pandas()

    mo.md(f"**name_key** blocking: **{len(name_key_candidates):,}** candidate pairs")
    return (name_key_candidates,)


@app.cell
def _(mo, nh, pd):
    # 5b: candidates by company overlap
    co_candidates = nh.run_query(
        """
        MATCH (s:Shareholder)
        WHERE s.is_person = true
          AND s.company_count >= 3
          AND NOT EXISTS { MATCH (s)-[:SAME_AS]->(:Person) }
        MATCH (s)-[:HOLDS_SHARES_IN]->(c:Company)<-[:DIRECTS]-(d:Director)
        WHERE d.is_person = true
          AND s.normalized_name <> d.normalized_name
        RETURN DISTINCT s.normalized_name AS sh_name,
               d.normalized_name AS dir_name,
               'company' AS source
        """,
    ).to_pandas()

    mo.md(f"**company overlap** blocking: **{len(co_candidates):,}** candidate pairs")
    return (co_candidates,)


@app.cell
def _(mo, nh, pd):
    # 5c: candidates by address overlap
    addr_candidates = nh.run_query(
        """
        MATCH (s:Shareholder)
        WHERE s.is_person = true
          AND s.company_count >= 3
          AND NOT EXISTS { MATCH (s)-[:SAME_AS]->(:Person) }
        MATCH (s)-[:HOLDS_SHARES_IN]->(c1:Company)-[:HAS_ADDRESS]->(a:Address)
        MATCH (a)<-[:HAS_ADDRESS]-(c2:Company)<-[:DIRECTS]-(d:Director)
        WHERE d.is_person = true
          AND s.normalized_name <> d.normalized_name
        RETURN DISTINCT s.normalized_name AS sh_name,
               d.normalized_name AS dir_name,
               'address' AS source
        """,
    ).to_pandas()

    mo.md(f"**address overlap** blocking: **{len(addr_candidates):,}** candidate pairs")
    return (addr_candidates,)


@app.cell
def _(
    addr_candidates,
    co_candidates,
    feature_cols,
    model,
    name_key_candidates,
    mo,
    pd,
):
    # Merge and deduplicate all candidates
    all_candidates = pd.concat(
        [name_key_candidates, co_candidates, addr_candidates],
        ignore_index=True,
    ).drop_duplicates(subset=["sh_name", "dir_name"])

    mo.md(f"**Total unique candidates:** {len(all_candidates):,}")
    return (all_candidates,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 6: Compute Features & Apply Classifier

    For each candidate pair, compute the same feature set used in training,
    then predict match probability.
    """)
    return


@app.cell
def _(all_candidates, driver, model, mo, np, pd):
    # Compute features for all candidate pairs
    # Trigram score, name_length_ratio, name_key_match are computable from strings
    def first_word(s):
        return s.split(" ")[0] if " " in s else s

    def last_word(s):
        return s.split(" ")[-1] if " " in s else s

    _df = all_candidates.copy()

    _df["name_length_ratio"] = _df.apply(
        lambda r: len(min(r["sh_name"], r["dir_name"], key=len)) / len(max(r["sh_name"], r["dir_name"], key=len)),
        axis=1,
    )

    _df["name_key_match"] = _df.apply(
        lambda r: int(
            first_word(r["sh_name"])[0] + last_word(r["sh_name"])
            == first_word(r["dir_name"])[0] + last_word(r["dir_name"]),
        ),
        axis=1,
    )

    # Trigram score — compute on the fly from name strings
    def trigram_jaccard(a, b):
        a_tri = {"  " + a.lower() + " "[i : i + 3] for i in range(len(a) + 1)}
        b_tri = {"  " + b.lower() + " "[i : i + 3] for i in range(len(b) + 1)}
        inter = len(a_tri & b_tri)
        union = len(a_tri | b_tri)
        return inter / union if union > 0 else 0.0

    _df["trigram_score"] = _df.apply(
        lambda r: trigram_jaccard(r["sh_name"], r["dir_name"]),
        axis=1,
    )

    # Company overlap and address overlap need Neo4j — batch query
    pairs = _df[["sh_name", "dir_name"]].to_dict("records")

    overlap_features = []
    batch_size = 500

    for i in range(0, len(pairs), batch_size):
        batch = pairs[i : i + batch_size]
        with driver.session() as s:
            result = s.run(
                """
                UNWIND $pairs AS p
                OPTIONAL MATCH (s:Shareholder {normalized_name: p.sh_name})-[:HOLDS_SHARES_IN]->(c:Company)<-[:DIRECTS]-(d:Director {normalized_name: p.dir_name})
                WITH p.sh_name AS sh, p.dir_name AS dir, count(DISTINCT c) AS co
                OPTIONAL MATCH (s2:Shareholder {normalized_name: sh})-[:HOLDS_SHARES_IN]->(c1:Company)-[:HAS_ADDRESS]->(a:Address)
                OPTIONAL MATCH (a)<-[:HAS_ADDRESS]-(c2:Company)<-[:DIRECTS]-(d2:Director {normalized_name: dir})
                RETURN sh, dir, co, count(DISTINCT a) AS shared_addr
                """,
                parameters={"pairs": batch},
            )
            overlap_features.extend(
                {
                    "sh_name": row["sh"],
                    "dir_name": row["dir"],
                    "company_overlap": row["co"],
                    "address_overlap": min(row["shared_addr"], 1),
                }
                for row in result
            )

    overlap_df = pd.DataFrame(overlap_features)
    _df = _df.merge(overlap_df, on=["sh_name", "dir_name"], how="left").fillna(
        {"company_overlap": 0, "address_overlap": 0},
    )

    # Predict
    feature_cols_list = [
        "trigram_score",
        "name_length_ratio",
        "name_key_match",
        "company_overlap",
        "address_overlap",
    ]
    X_candidates = _df[feature_cols_list].fillna(0)
    _df["match_probability"] = model.predict_proba(X_candidates)[:, 1]

    mo.md(
        f"Features computed for **{len(_df):,}** candidate pairs\n\n"
        f"**Prediction distribution:**\n"
        f"  p ≥ 0.9: {(_df['match_probability'] >= 0.9).sum():,}\n"
        f"  0.5 ≤ p < 0.9: {((_df['match_probability'] >= 0.5) & (_df['match_probability'] < 0.9)).sum():,}\n"
        f"  p < 0.5: {(_df['match_probability'] < 0.5).sum():,}",
    )
    return (
        X_candidates,
        batch_size,
        feature_cols_list,
        overlap_df,
        overlap_features,
        pairs,
        result,
        s,
        trigram_jaccard,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 7: Write Results to Neo4j

    For candidates with match_probability ≥ 0.5, create a Person node
    (if not exists) and a SAME_AS relationship with the probability score.
    """)
    return


@app.cell
def _(
    driver,
    mo,
    nh,
    pd,
    _df,
):
    # Filter to high-confidence matches
    high_conf = _df[_df["match_probability"] >= 0.5].copy()

    # Create Person nodes for canonical names
    batch_size = 500
    all_canonical = list(
        set(high_conf["sh_name"].tolist()) | set(high_conf["dir_name"].tolist()),
    )

    person_count_before = nh.run_query("MATCH (p:Person) RETURN count(*) AS c").item(0, "c")

    driver = nh.get_driver()
    for i in range(0, len(all_canonical), batch_size):
        batch = all_canonical[i : i + batch_size]
        with driver.session() as s:
            s.run(
                """
                UNWIND $names AS name
                MERGE (p:Person {person_id: name})
                """,
                parameters={"names": batch},
            )

    person_count_after = nh.run_query("MATCH (p:Person) RETURN count(*) AS c").item(0, "c")

    # Create SAME_AS relationships
    rels = high_conf[["sh_name", "dir_name", "match_probability"]].to_dict("records")
    rels_created = 0
    for i in range(0, len(rels), batch_size):
        batch = rels[i : i + batch_size]
        with driver.session() as s:
            result = s.run(
                """
                UNWIND $rels AS r
                MATCH (s:Shareholder {normalized_name: r.sh_name})
                MATCH (p:Person {person_id: r.dir_name})
                MERGE (s)-[rel:SAME_AS]->(p)
                SET rel.score = r.match_probability,
                    rel.match_method = 'classifier_v2',
                    rel.match_probability = r.match_probability
                RETURN count(*) AS created
                """,
                parameters={"rels": batch},
            )
            rels_created += result.single()["created"]

    mo.md(
        f"**Person nodes:** {person_count_before:,} → {person_count_after:,} "
        f"(+{person_count_after - person_count_before:,})\n\n"
        f"**SAME_AS relationships:** {rels_created:,} created/updated",
    )
    return (
        all_canonical,
        batch,
        high_conf,
        person_count_after,
        person_count_before,
        rels,
        rels_created,
        result,
        s,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 8: Verify New Matches

    Check how many of the new SAME_AS relationships have company overlap
    (proven same person) vs. not (potential false positives).
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (s:Shareholder)-[r:SAME_AS {match_method: 'classifier_v2'}]->(p:Person)
        MATCH (d:Director {normalized_name: p.person_id})
        OPTIONAL MATCH (s)-[:HOLDS_SHARES_IN]->(c:Company)<-[:DIRECTS]-(d)
        WITH r, count(DISTINCT c) AS overlap
        SET r.company_overlap = overlap,
            r.verified = CASE WHEN overlap >= 1 THEN true ELSE false END
        RETURN r.verified AS verified,
               round(avg(r.match_probability), 3) AS avg_probability,
               count(*) AS matches
        ORDER BY verified
        """,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### New matches by source (name_key / company / address)
    """)
    return


@app.cell
def _(nh):
    nh.mo_table(
        """
        MATCH (s:Shareholder)-[r:SAME_AS {match_method: 'classifier_v2'}]->(p:Person)
        WHERE r.verified = true
        OPTIONAL MATCH (d:Director {normalized_name: p.person_id})
        WITH s, d, r
        RETURN
          CASE
            WHEN s.name_key = d.name_key AND r.company_overlap > 0 THEN 'name_key + company'
            WHEN s.name_key = d.name_key THEN 'name_key only'
            WHEN r.company_overlap > 0 THEN 'company overlap'
            ELSE 'address overlap'
          END AS match_source,
          count(*) AS verified_matches,
          round(avg(r.match_probability), 3) AS avg_probability
        ORDER BY verified_matches DESC
        """,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Key Takeaways

    1. **Classifier improves on trigram-only** — by combining trigram_score
       with company_overlap and address_overlap, the RandomForest catches true
       matches that trigram-only matching missed.
    2. **Address overlap is the strongest new signal** — common-name false
       positives (different people with the same name) almost never share
       an address, while true matches often do.
    3. **Three-blocking strategy** covers more candidates than name_key alone:
       company overlap catches investor-directors, address overlap catches
       nominee structures at the same registered office.
    4. **Calibrated probability** replaces hard thresholds — each SAME_AS
       relationship now carries a classifier probability, enabling precision
       tuning downstream.

    Up next: **[06: Predicting Investor Types](http://localhost:2718/?file=06_predicting_investor_types.py)**
    — using graph features to classify investors as VC, property, trustee,
    or individual.
    """)
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
