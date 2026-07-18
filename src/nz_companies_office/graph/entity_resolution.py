"""Entity resolution: identify the same person across Shareholder and Director nodes."""

from __future__ import annotations

import logging
import time

from nz_companies_office.db.connection import get_driver
from nz_companies_office.db.repository import Neo4jRepository

logger = logging.getLogger(__name__)

TRIGRAM_MIN_SCORE = 0.55
TRIGRAM_HIGH_CONFIDENCE = 0.65
MIN_COMPANY_COUNT = 3

_NORMALISE_QUERY = """
    MATCH (s:Shareholder)
    SET s.normalized_name = trim(apoc.text.replace(s.name, '\\\\s+', ' '))
"""
_NORMALISE_DIRECTOR_QUERY = """
    MATCH (d:Director)
    SET d.normalized_name = trim(apoc.text.replace(d.name, '\\\\s+', ' '))
"""
_PERSON_ID_QUERY = """
    MATCH (s:Shareholder)
    SET s.person_id = s.normalized_name,
        s.is_person = CASE WHEN s.normalized_name =~ '.*[a-z].*' THEN true ELSE false END
"""
_PERSON_ID_DIRECTOR_QUERY = """
    MATCH (d:Director)
    SET d.person_id = d.normalized_name,
        d.is_person = CASE WHEN d.normalized_name =~ '.*[a-z].*' THEN true ELSE false END
"""
_NAME_KEY_QUERY = """
    MATCH (s:Shareholder)
    SET s.name_key = toUpper(split(s.normalized_name, ' ')[0])
                    + toUpper(split(s.normalized_name, ' ')[-1])
"""
_NAME_KEY_DIRECTOR_QUERY = """
    MATCH (d:Director)
    SET d.name_key = toUpper(split(d.normalized_name, ' ')[0])
                    + toUpper(split(d.normalized_name, ' ')[-1])
"""
_TRIGRAM_QUERY = """
    MATCH (n)
    WHERE (n:Shareholder OR n:Director) AND n.normalized_name IS NOT NULL
    WITH n, toLower(n.normalized_name) AS clean
    WITH n, '  ' + clean + ' ' AS padded
    SET n.trigrams = [i IN range(0, size(padded) - 3) | substring(padded, i, 3)]
"""
_INDEX_NORM_QUERY = "CREATE INDEX IF NOT EXISTS FOR (s:Shareholder) ON (s.normalized_name)"
_INDEX_NORM_DIR_QUERY = "CREATE INDEX IF NOT EXISTS FOR (d:Director) ON (d.normalized_name)"
_INDEX_KEY_QUERY = "CREATE INDEX IF NOT EXISTS FOR (s:Shareholder) ON (s.name_key)"
_INDEX_KEY_DIR_QUERY = "CREATE INDEX IF NOT EXISTS FOR (d:Director) ON (d.name_key)"
_EXACT_MATCH_QUERY = """
    MATCH (s:Shareholder {is_person: true})
    MATCH (d:Director {normalized_name: s.normalized_name, is_person: true})
    MERGE (p:Person {person_id: s.normalized_name})
    MERGE (s)-[:SAME_AS {score: 1.0, confidence: 'exact', match_method: 'exact'}]->(p)
    MERGE (d)-[:SAME_AS {score: 1.0, confidence: 'exact', match_method: 'exact'}]->(p)
    RETURN count(*) AS created
"""
_FUZZY_CANDIDATES_QUERY = """
    MATCH (s:Shareholder)
    WHERE s.is_person = true
      AND s.company_count >= $min_company_count
      AND s.name_key IS NOT NULL AND s.trigrams IS NOT NULL
      AND NOT EXISTS { MATCH (s)-[:SAME_AS]->(:Person) }
    WITH s
    MATCH (d:Director)
    WHERE d.name_key = s.name_key
      AND d.is_person = true
      AND d.trigrams IS NOT NULL
      AND s.normalized_name <> d.normalized_name
    WITH s, d,
         size([x IN s.trigrams WHERE x IN d.trigrams]) * 1.0
           / (size(s.trigrams) + size(d.trigrams)
              - size([x IN s.trigrams WHERE x IN d.trigrams])) AS jaccard
    WHERE jaccard >= $min_score
    RETURN s.normalized_name AS sh_name,
           d.normalized_name AS dir_name,
           jaccard AS trigram_score,
           s.name_key AS name_key
    ORDER BY jaccard DESC
"""
_OVERLAP_QUERY = """
    UNWIND $pairs AS p
    OPTIONAL MATCH (s:Shareholder {normalized_name: p.sh_name})-[:HOLDS_SHARES_IN]->(c:Company)<-[:DIRECTS]-(d:Director {normalized_name: p.dir_name})
    WITH p.sh_name AS sh, p.dir_name AS dir, count(DISTINCT c) AS co
    OPTIONAL MATCH (s2:Shareholder {normalized_name: sh})-[:HOLDS_SHARES_IN]->(c1:Company)-[:HAS_ADDRESS]->(a:Address)
    OPTIONAL MATCH (a)<-[:HAS_ADDRESS]-(c2:Company)<-[:DIRECTS]-(d2:Director {normalized_name: dir})
    RETURN sh, dir, co, count(DISTINCT a) AS shared_addr
"""
_WRITE_PERSONS_QUERY = """
    UNWIND $names AS name
    MERGE (p:Person {person_id: name})
"""
_WRITE_SAME_AS_QUERY = """
    UNWIND $rels AS r
    MATCH (s:Shareholder {normalized_name: r.sh_name})
    MATCH (p:Person {person_id: r.person_id})
    MERGE (s)-[rel:SAME_AS]->(p)
    SET rel.score = r.score,
        rel.confidence = r.confidence,
        rel.company_overlap = r.company_overlap,
        rel.verified = r.verified,
        rel.match_method = 'trigram'
"""
_LINK_INVESTOR_DIRECTORS_QUERY = """
    MATCH (s:Shareholder)-[r:SAME_AS {verified: true}]->(p:Person)
    MATCH (d:Director {normalized_name: p.person_id})
    WITH s, d, count(DISTINCT ()-[:HOLDS_SHARES_IN]->(c:Company)<-[:DIRECTS]-()) AS overlap
    WHERE overlap >= 1
    MERGE (s)-[rel:IS_INVESTOR_DIRECTOR]->(d)
    SET rel.company_overlap = overlap
    RETURN count(*) AS created
"""
WIPE_QUERY = """
    MATCH (p:Person) DETACH DELETE p
"""
PERSON_COUNT_QUERY = "MATCH (p:Person) RETURN count(*) AS c"
SAME_AS_COUNT_QUERY = "MATCH ()-[r:SAME_AS]->() RETURN count(*) AS c"
IID_COUNT_QUERY = "MATCH ()-[r:IS_INVESTOR_DIRECTOR]->() RETURN count(*) AS c"
_COMPANY_COUNT_QUERY = """
    MATCH (s:Shareholder)-[:HOLDS_SHARES_IN]->(c:Company)
    WITH s, count(DISTINCT c) AS cnt
    SET s.company_count = cnt
"""


def _trigram_jaccard(a: str, b: str) -> float:
    """Compute Jaccard similarity between the trigram sets of two strings."""

    def _trigrams(s: str) -> set[str]:
        padded = "  " + s.lower() + " "
        return {padded[i : i + 3] for i in range(len(padded) - 2)}

    a_tri = _trigrams(a)
    b_tri = _trigrams(b)
    inter = len(a_tri & b_tri)
    union = len(a_tri | b_tri)
    return inter / union if union > 0 else 0.0


def normalize_names(repo: Neo4jRepository) -> int:
    """Set normalized_name, name_key, is_person on all Shareholder and Director nodes.

    Returns:
        Count of nodes updated.

    """
    t0 = time.perf_counter()
    repo.run_query(_NORMALISE_QUERY)
    repo.run_query(_NORMALISE_DIRECTOR_QUERY)
    repo.run_query(_PERSON_ID_QUERY)
    repo.run_query(_PERSON_ID_DIRECTOR_QUERY)
    repo.run_query(_INDEX_NORM_QUERY)
    repo.run_query(_INDEX_NORM_DIR_QUERY)
    repo.run_query(_NAME_KEY_QUERY)
    repo.run_query(_NAME_KEY_DIRECTOR_QUERY)
    repo.run_query(_INDEX_KEY_QUERY)
    repo.run_query(_INDEX_KEY_DIR_QUERY)
    elapsed = time.perf_counter() - t0
    count = repo.run_query("MATCH (n:Shareholder) WHERE n.is_person IS NOT NULL RETURN count(*) AS c")[0]["c"]
    logger.info("Normalized %d nodes (%.2f s)", count, elapsed)
    return count


def compute_trigrams(repo: Neo4jRepository) -> int:
    """Compute trigram arrays on all Shareholder and Director nodes.

    Returns:
        Count of nodes updated.

    """
    t0 = time.perf_counter()
    repo.run_query(_TRIGRAM_QUERY)
    elapsed = time.perf_counter() - t0
    count = repo.run_query("MATCH (n) WHERE n.trigrams IS NOT NULL RETURN count(*) AS c")[0]["c"]
    logger.info("Computed trigrams on %d nodes (%.2f s)", count, elapsed)
    return count


def compute_company_counts(repo: Neo4jRepository) -> int:
    """Set company_count on all Shareholder nodes.

    Returns:
        Count of nodes updated.

    """
    t0 = time.perf_counter()
    repo.run_query(_COMPANY_COUNT_QUERY)
    elapsed = time.perf_counter() - t0
    count = repo.run_query("MATCH (s:Shareholder) WHERE s.company_count IS NOT NULL RETURN count(*) AS c")[0]["c"]
    logger.info("Computed company_count on %d shareholders (%.2f s)", count, elapsed)
    return count


def exact_match(repo: Neo4jRepository) -> int:
    """Create Person + SAME_AS for exact normalized_name matches.

    Returns:
        Count of SAME_AS relationships created.

    """
    t0 = time.perf_counter()
    result = repo.run_query(_EXACT_MATCH_QUERY)
    elapsed = time.perf_counter() - t0
    created = result[0]["created"] if result else 0
    logger.info("Exact matches: %d SAME_AS created (%.2f s)", created, elapsed)
    return created


def fuzzy_match_candidates(repo: Neo4jRepository) -> list[dict]:
    """Find candidate pairs via name_key blocking + trigram Jaccard.

    Returns:
        List of dicts with sh_name, dir_name, trigram_score, name_key.

    """
    t0 = time.perf_counter()
    rows = repo.run_query(
        _FUZZY_CANDIDATES_QUERY,
        min_company_count=MIN_COMPANY_COUNT,
        min_score=TRIGRAM_MIN_SCORE,
    )
    elapsed = time.perf_counter() - t0
    logger.info("Fuzzy candidates: %d pairs found (%.2f s)", len(rows), elapsed)
    return rows


def verify_candidates(repo: Neo4jRepository, candidates: list[dict]) -> list[dict]:
    """Score candidates with company_overlap + address_overlap via batched queries.

    Args:
        repo: Neo4j repository instance.
        candidates: List of dicts from fuzzy_match_candidates.

    Returns:
        Same list with company_overlap and address_overlap fields added.

    """
    if not candidates:
        return candidates

    t0 = time.perf_counter()
    batch_size = 500
    enriched = []

    for i in range(0, len(candidates), batch_size):
        batch = [{"sh_name": c["sh_name"], "dir_name": c["dir_name"]} for c in candidates[i : i + batch_size]]
        rows = repo.run_query(_OVERLAP_QUERY, pairs=batch)
        overlap_map = {(r["sh"], r["dir"]): r for r in rows}

        for c in candidates[i : i + batch_size]:
            key = (c["sh_name"], c["dir_name"])
            ov = overlap_map.get(key, {})
            enriched.append(
                {
                    **c,
                    "company_overlap": ov.get("co", 0),
                    "address_overlap": min(ov.get("shared_addr", 0), 1),
                },
            )

    elapsed = time.perf_counter() - t0
    verified = sum(1 for c in enriched if c["company_overlap"] >= 1)
    logger.info(
        "Verified %d / %d candidates (%.2f s)",
        verified,
        len(enriched),
        elapsed,
    )
    return enriched


def write_matches(repo: Neo4jRepository, candidates: list[dict]) -> tuple[int, int]:
    """Create Person nodes + SAME_AS relationships for scored candidates.

    Args:
        repo: Neo4j repository instance.
        candidates: Verified candidates with trigram_score, company_overlap,
            address_overlap fields.

    Returns:
        Tuple of (person_count, same_as_count).

    """
    t0 = time.perf_counter()

    to_write = []
    for c in candidates:
        score = c["trigram_score"]
        co = c["company_overlap"]
        verified = co >= 1
        if score >= TRIGRAM_HIGH_CONFIDENCE or verified:
            confidence = "high" if score >= TRIGRAM_HIGH_CONFIDENCE else "medium"
            to_write.append(
                {
                    "sh_name": c["sh_name"],
                    "person_id": c["dir_name"],
                    "score": score,
                    "confidence": confidence,
                    "company_overlap": co,
                    "verified": verified,
                },
            )

    if not to_write:
        logger.info("No matches to write")
        return 0, 0

    # Collect unique person IDs
    person_ids = list({r["person_id"] for r in to_write})
    for i in range(0, len(person_ids), 500):
        repo.run_query(_WRITE_PERSONS_QUERY, names=person_ids[i : i + 500])

    # Write SAME_AS relationships in batches
    rels_created = 0
    for i in range(0, len(to_write), 500):
        batch = to_write[i : i + 500]
        result = repo.run_query(_WRITE_SAME_AS_QUERY, rels=batch)
        rels_created += result[0]["created"] if result else 0

    elapsed = time.perf_counter() - t0
    person_count = repo.run_query(PERSON_COUNT_QUERY)[0]["c"]
    logger.info(
        "Wrote %d Person nodes, %d SAME_AS rels (%.2f s)",
        person_count,
        rels_created,
        elapsed,
    )
    return person_count, rels_created


def link_investor_directors(repo: Neo4jRepository) -> int:
    """Create IS_INVESTOR_DIRECTOR for verified same-company pairs.

    Returns:
        Count of relationships created.

    """
    t0 = time.perf_counter()
    result = repo.run_query(_LINK_INVESTOR_DIRECTORS_QUERY)
    elapsed = time.perf_counter() - t0
    created = result[0]["created"] if result else 0
    logger.info("IS_INVESTOR_DIRECTOR: %d relationships created (%.2f s)", created, elapsed)
    return created


def entity_resolution() -> None:
    """Full entity resolution pipeline.

    Wipes existing Person/SAME_AS nodes, then runs all stages:
    normalize → trigrams → company_counts → exact_match → fuzzy_match
    → verify → write → link_investor_directors.

    Raises:
        RuntimeError: If Neo4j connection fails.

    """
    pipeline_start = time.perf_counter()
    repo = Neo4jRepository(get_driver())
    repo.ensure_connected()

    # Wipe existing Person nodes
    t0 = time.perf_counter()
    repo.run_query(WIPE_QUERY)
    elapsed = time.perf_counter() - t0
    logger.info("Wiped existing Person nodes (%.2f s)", elapsed)

    # Pipeline stages
    normalize_names(repo)
    compute_company_counts(repo)
    compute_trigrams(repo)
    exact_match(repo)

    candidates = fuzzy_match_candidates(repo)
    candidates = verify_candidates(repo, candidates)
    write_matches(repo, candidates)
    link_investor_directors(repo)

    # Final summary
    person_count = repo.run_query(PERSON_COUNT_QUERY)[0]["c"]
    same_as_count = repo.run_query(SAME_AS_COUNT_QUERY)[0]["c"]
    iid_count = repo.run_query(IID_COUNT_QUERY)[0]["c"]

    total_elapsed = time.perf_counter() - pipeline_start
    logger.info("--- Entity Resolution Summary ---")
    logger.info("  Person nodes:            %d", person_count)
    logger.info("  SAME_AS relationships:   %d", same_as_count)
    logger.info("  IS_INVESTOR_DIRECTOR:    %d", iid_count)
    logger.info("  Total time:              %.2f s", total_elapsed)
