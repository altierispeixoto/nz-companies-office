// =============================================================================
// Graph exploration queries for NZ Companies Office data
// =============================================================================

// ---------------------------------------------------------------------------
// 1. Co-investor chains from a starting shareholder
// ---------------------------------------------------------------------------

// 1a. Who invested in company X, and what else did they invest in?
//     (find all shareholders of Auror, then their other companies)
MATCH (auror:Company)
WHERE toLower(auror.name) = 'auror limited'
MATCH (s:Shareholder)-[auror_edge:HOLDS_SHARES_IN]->(auror)
MATCH (s)-[other_edge:HOLDS_SHARES_IN]->(other:Company)
WHERE other <> auror
RETURN s.name AS shareholder,
       auror_edge.shares AS shares_in_auror,
       other.name AS also_invested_in,
       other_edge.shares AS shares_in_other,
       COUNT { (s)-[:HOLDS_SHARES_IN]->() } AS total_companies
ORDER BY total_companies DESC
LIMIT 25;

// 1b. 4-shareholder chain: S1 → C1 ← S2 → C2 ← S3 → C3 ← S4
MATCH (s1:Shareholder)-[:HOLDS_SHARES_IN]->(c1:Company)<-[:HOLDS_SHARES_IN]-(s2:Shareholder)
WHERE toLower(s1.name) CONTAINS 'punakaiki'
  AND s2 <> s1
WITH DISTINCT s2
MATCH (s2)-[:HOLDS_SHARES_IN]->(c2:Company)<-[:HOLDS_SHARES_IN]-(s3:Shareholder)
WHERE s3 <> s2
  AND NOT toLower(s3.name) CONTAINS 'punakaiki'
WITH DISTINCT s3
MATCH (s3)-[:HOLDS_SHARES_IN]->(c3:Company)<-[:HOLDS_SHARES_IN]-(s4:Shareholder)
WHERE s4 <> s3
  AND NOT toLower(s4.name) CONTAINS 'punakaiki'
RETURN s4.name AS shareholder_4,
       count(DISTINCT s3) AS intermediate_s3s,
       count(*) AS total_paths
ORDER BY total_paths DESC
LIMIT 20;

// ---------------------------------------------------------------------------
// 2. Director analysis
// ---------------------------------------------------------------------------

// 2a. Top multi-company directors (by number of companies directed)
MATCH (d:Director)-[:DIRECTS]->(c:Company)
RETURN d.name AS director,
       count(DISTINCT c) AS companies,
       collect(DISTINCT c.name)[0..3] AS examples
ORDER BY companies DESC
LIMIT 20;

// 2b. Director-shareholder overlap: people who sit on the board AND hold
//     shares in the same company (matched by name across both labels)
MATCH (d:Director)-[:DIRECTS]->(c:Company)<-[:HOLDS_SHARES_IN]-(s:Shareholder)
WHERE d.name = s.name
RETURN d.name AS person,
       count(DISTINCT c) AS overlap_companies
ORDER BY overlap_companies DESC
LIMIT 20;

// ---------------------------------------------------------------------------
// 3. Shareholder analysis
// ---------------------------------------------------------------------------

// 3a. Companies with the largest number of shareholders
MATCH (s:Shareholder)-[:HOLDS_SHARES_IN]->(c:Company)
RETURN c.name AS company,
       c.company_number AS number,
       count(DISTINCT s) AS shareholders
ORDER BY shareholders DESC
LIMIT 20;

// 3b. Shareholders that appear in the most DIFFERENT companies
MATCH (s:Shareholder)-[:HOLDS_SHARES_IN]->(c:Company)
RETURN s.name AS shareholder,
       count(DISTINCT c) AS companies,
       collect(DISTINCT c.name)[0..3] AS examples
ORDER BY companies DESC
LIMIT 20;

// 3c. Most frequent co-investor pairs: pairs of shareholders that
//     co-invest in the most companies together.
//     Uses id(s1) < id(s2) to avoid duplicate pairs (A,B) / (B,A).
MATCH (s1:Shareholder)-[:HOLDS_SHARES_IN]->(c:Company)<-[:HOLDS_SHARES_IN]-(s2:Shareholder)
WHERE s1 < s2
RETURN s1.name AS shareholder_a,
       s2.name AS shareholder_b,
       count(DISTINCT c) AS shared_companies
ORDER BY shared_companies DESC
LIMIT 20;

// 3d. Most connected co-investors: shareholders who co-invest with the
//     highest number of OTHER distinct shareholders
MATCH (s1:Shareholder)-[:HOLDS_SHARES_IN]->(c:Company)<-[:HOLDS_SHARES_IN]-(s2:Shareholder)
WHERE s1 <> s2
WITH s1, count(DISTINCT s2) AS co_investors
RETURN s1.name AS shareholder,
       co_investors
ORDER BY co_investors DESC
LIMIT 20;

// 3e. Tight shareholder triangles (cliques): 3 shareholders where every
//     pair co-invests in >= 10 companies together.
//     Filters out most trustee/nominee/custodian entities to surface
//     real business syndicates.
MATCH (s1:Shareholder)-[:HOLDS_SHARES_IN]->(c:Company)<-[:HOLDS_SHARES_IN]-(s2:Shareholder)
WHERE id(s1) < id(s2)
  AND NOT toLower(s1.name) CONTAINS 'trustee'
  AND NOT toLower(s2.name) CONTAINS 'trustee'
  AND NOT toLower(s1.name) CONTAINS 'nominee'
  AND NOT toLower(s2.name) CONTAINS 'nominee'
  AND NOT toLower(s1.name) CONTAINS 'custodian'
  AND NOT toLower(s2.name) CONTAINS 'custodian'
WITH s1, s2, count(DISTINCT c) AS w
WHERE w >= 10

MATCH (s1)-[:HOLDS_SHARES_IN]->(c2:Company)<-[:HOLDS_SHARES_IN]-(s3:Shareholder)
WHERE id(s2) < id(s3) AND s3 <> s1
  AND NOT toLower(s3.name) CONTAINS 'trustee'
  AND NOT toLower(s3.name) CONTAINS 'nominee'
  AND NOT toLower(s3.name) CONTAINS 'custodian'
WITH s1, s2, s3, w
MATCH (s2)-[:HOLDS_SHARES_IN]->(c3:Company)<-[:HOLDS_SHARES_IN]-(s3)
WHERE id(s1) < id(s3)
WITH s1, s2, s3, w AS ab, count(DISTINCT c3) AS bc
WHERE bc >= 10

MATCH (s1)-[:HOLDS_SHARES_IN]->(c4:Company)<-[:HOLDS_SHARES_IN]-(s3)
WHERE id(s1) < id(s3)
WITH s1, s2, s3, ab, bc, count(DISTINCT c4) AS ac
WHERE ac >= 10

RETURN s1.name AS a, s2.name AS b, s3.name AS c,
       ab, bc, ac, ab + bc + ac AS total
ORDER BY total DESC
LIMIT 30;

// 3f. Wider cluster: find shareholders connected to ANY of N known
//     cluster anchors (e.g. the ARL trustee group) with strong ties.
//     Replace the anchor names to explore different clusters.
MATCH (anchor:Shareholder)
WHERE anchor.name IN [
  'Benedict John Joseph SHEEHAN',
  'Jason John TAYLOR',
  'Rebecca Rachael DICKIE'
]
WITH collect(anchor) AS anchors
UNWIND anchors AS a
MATCH (a)-[:HOLDS_SHARES_IN]->(c:Company)<-[:HOLDS_SHARES_IN]-(s:Shareholder)
WHERE s <> a
WITH s, a, count(DISTINCT c) AS weight
WHERE weight >= 10
WITH s, collect(a.name) AS connected_to, sum(weight) AS total_weight, count(*) AS ties
WHERE ties >= 3
RETURN s.name AS cluster_member,
       ties AS connects_to_n_of_3,
       total_weight,
       connected_to
ORDER BY total_weight DESC
LIMIT 20;

// ---------------------------------------------------------------------------
// 4. Trustee / nominee / custodian patterns
// ---------------------------------------------------------------------------

// 4a. Top trustee/custodian/nominee shareholders
MATCH (s:Shareholder)-[:HOLDS_SHARES_IN]->(c:Company)
WHERE toLower(s.name) CONTAINS 'trustee'
   OR toLower(s.name) CONTAINS 'custodian'
   OR toLower(s.name) CONTAINS 'nominee'
RETURN s.name AS trustee,
       count(DISTINCT c) AS companies
ORDER BY companies DESC
LIMIT 20;

// ---------------------------------------------------------------------------
// 6. GDS — Graph Data Science community detection (requires GDS plugin)
//     docker-compose.yml: NEO4J_PLUGINS: '["apoc", "graph-data-science"]'
// ---------------------------------------------------------------------------

// 6a. Create weighted co-investment relationships for strong ties (>= 5
//     shared companies) — required before projecting a GDS graph.
MATCH (s1:Shareholder)-[:HOLDS_SHARES_IN]->(c:Company)<-[:HOLDS_SHARES_IN]-(s2:Shareholder)
WHERE elementId(s1) < elementId(s2)
WITH s1, s2, count(DISTINCT c) AS weight
WHERE weight >= 5
MERGE (s1)-[r:CO_INVESTS_WITH]-(s2)
SET r.weight = weight;

// 6b. Project weighted co-investment graph into GDS in-memory graph
CALL gds.graph.project(
  'coinvest',
  'Shareholder',
  {
    CO_INVESTS_WITH: {
      orientation: 'UNDIRECTED',
      properties: ['weight']
    }
  }
);

// 6c. Run Louvain community detection
CALL gds.louvain.stream('coinvest', { relationshipWeightProperty: 'weight' })
YIELD nodeId, communityId, intermediateCommunityIds
WITH gds.util.asNode(nodeId).name AS shareholder, communityId
RETURN communityId,
       count(*) AS members,
       collect(shareholder) AS shareholders
ORDER BY members DESC
LIMIT 30;

// 6d. Look up which community a specific shareholder belongs to
MATCH (s:Shareholder)
WHERE s.name IN ['Benedict John Joseph SHEEHAN', 'Jason John TAYLOR']
CALL gds.louvain.stream('coinvest', { relationshipWeightProperty: 'weight' })
YIELD nodeId, communityId
WHERE gds.util.asNode(nodeId) = s
RETURN s.name AS shareholder, communityId;

// 6e. List all members of a specific community (replace 60564 with your ID)
CALL gds.louvain.stream('coinvest', { relationshipWeightProperty: 'weight' })
YIELD nodeId, communityId
WHERE communityId = 60564
RETURN gds.util.asNode(nodeId).name AS member
ORDER BY member;

// ---------------------------------------------------------------------------
// 6h. GDS — Graph metrics (centrality, influence, clustering)
//     Requires the 'coinvest' graph projected as UNDIRECTED in step 6b.
// ---------------------------------------------------------------------------

// 6h-i. Degree Centrality: count of distinct co-investment partners
CALL gds.degree.stream('coinvest', { relationshipWeightProperty: 'weight' })
YIELD nodeId, score
WITH gds.util.asNode(nodeId).name AS shareholder, score AS connections
RETURN shareholder, connections
ORDER BY connections DESC
LIMIT 15;

// 6h-ii. Weighted Degree: total shared companies across all partners
CALL gds.degree.stream('coinvest', { relationshipWeightProperty: 'weight', orientation: 'UNDIRECTED' })
YIELD nodeId, score
WITH gds.util.asNode(nodeId).name AS shareholder, score AS total_shared_companies
RETURN shareholder, total_shared_companies
ORDER BY total_shared_companies DESC
LIMIT 15;

// 6h-iii. PageRank: 'influence' — co-invests with well-connected partners
CALL gds.pageRank.stream('coinvest', { relationshipWeightProperty: 'weight', maxIterations: 20 })
YIELD nodeId, score
WITH gds.util.asNode(nodeId).name AS shareholder, score
RETURN shareholder, score
ORDER BY score DESC
LIMIT 15;

// 6h-iv. Local Clustering Coefficient (LCC):
//        1.0 = all their co-investors also co-invest with each other (tight clique)
//        0.0 = star connector (none of their co-investors know each other)
CALL gds.localClusteringCoefficient.stream('coinvest')
YIELD nodeId, localClusteringCoefficient
WITH gds.util.asNode(nodeId).name AS shareholder, localClusteringCoefficient AS lcc
RETURN shareholder, lcc
ORDER BY lcc DESC
LIMIT 10;

// 6h-v. LOWEST LCC — bridge nodes connecting different communities
CALL gds.localClusteringCoefficient.stream('coinvest')
YIELD nodeId, localClusteringCoefficient
WITH gds.util.asNode(nodeId).name AS shareholder, localClusteringCoefficient AS lcc
WHERE lcc > 0
RETURN shareholder, lcc
ORDER BY lcc ASC
LIMIT 15;

// 6h-vi. Compare all metrics for a custom set of shareholders
WITH [
  'Paayal  GARG', 'Himanshu  MITTAL', 'Abhinav  GUPTA',
  'ICEHOUSE VENTURES NOMINEES LIMITED', 'ASPIRE NZ SEED FUND LIMITED',
  'Benedict John Joseph SHEEHAN', 'Jason John TAYLOR',
  'Ranald Craig PATERSON', 'Philip Henschel CAESAR',
  'NEW ZEALAND TRUSTEE SERVICES LIMITED', 'CUSTODIAL SERVICES LIMITED',
  'David Saul BRISCOE', 'Rebecca Rachael DICKIE'
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
ORDER BY pagerank DESC;

// ---------------------------------------------------------------------------
// 6i. GDS — Graph embeddings (Node2Vec)
//     Must run 6i-i first to write embeddings, then 6i-ii for similarity.
//     Requires 'coinvest' graph projected WITH {embedding} property.
// ---------------------------------------------------------------------------

// 6i-i. Generate & write Node2Vec embeddings (32-dim) as node property
CALL gds.node2vec.write('coinvest', {
  embeddingDimension: 32,
  walkLength: 10,
  walksPerNode: 10,
  windowSize: 5,
  relationshipWeightProperty: 'weight',
  writeProperty: 'embedding'
})
YIELD nodePropertiesWritten, writeMillis;

// 6i-ii. Find shareholders most similar to a given one (by cosine similarity)
//        Replace the anchor name to query different investors.
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
LIMIT 20;

// ---------------------------------------------------------------------------
// 6j. Node Classification via Embedding kNN
//     Requires embeddings written (6i-i) and GDS graph projected with them.
// ---------------------------------------------------------------------------

// 6j-i. Write seed labels as a temporary node property
MATCH (s:Shareholder)
WHERE s.name IN [
  'ICEHOUSE VENTURES NOMINEES LIMITED',
  'ASPIRE NZ SEED FUND LIMITED',
  'K ONE W ONE (NO 4) LIMITED',
  'ANGEL HQ NOMINEE LIMITED'
]
SET s.label = 'VC';

MATCH (s:Shareholder)
WHERE s.name IN [
  'Himanshu  MITTAL', 'Abhinav  GUPTA', 'Shivali  DUTTA',
  'Bunleng  CHHUN', 'Srinivas  MEKALA'
]
SET s.label = 'PROPERTY';

MATCH (s:Shareholder)
WHERE s.name IN [
  'Benedict John Joseph SHEEHAN', 'Jason John TAYLOR',
  'Rebecca Rachael DICKIE'
]
SET s.label = 'TRUSTEE';

MATCH (s:Shareholder)
WHERE s.name IN [
  'David Saul BRISCOE', 'Hamish Gordon WALKER',
  'Alysha Margaret HINTON', 'Kate Frances MITCHELL'
]
SET s.label = 'ACCOUNTING';

// 6j-ii. Classify all shareholders with co-investment edges.
//        For each target, compute avg cosine similarity to seeds in each
//        class, then predict the class with the highest average similarity.
//        Collects seeds once into a list for efficiency.
//        Also counts how many companies each shareholder invests in.
//   NOTE: Classification quality depends heavily on seed selection.
//         With only 16 seeds, large trustee firms (NZ Trustee Services)
//         may be misclassified as PROPERTY because the ARL trustee seeds
//         represent a narrower law-firm trustee profile. Add more diverse
//         seed labels to improve accuracy.
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

// Optional: write predictions as node property
// MATCH (s:Shareholder {name: shareholder})
// SET s.predicted_label = predicted

// Count companies each target invests in
OPTIONAL MATCH (target)-[:HOLDS_SHARES_IN]->(c:Company)
WITH target.name AS shareholder, predicted, count(DISTINCT c) AS companies

RETURN predicted AS class,
       count(*) AS count,
       avg(companies) AS avg_companies,
       max(companies) AS max_companies
ORDER BY count DESC;

// 6j-ii-alt. Top N classified shareholders by company count
MATCH (s:Shareholder)
WHERE s.predicted_label IS NOT NULL
OPTIONAL MATCH (s)-[:HOLDS_SHARES_IN]->(c:Company)
RETURN s.name AS shareholder,
       s.predicted_label AS predicted,
       count(DISTINCT c) AS companies
ORDER BY companies DESC
LIMIT 30;

// 6j-iii. Clean up temporary label property
MATCH (s:Shareholder)
WHERE s.label IS NOT NULL
REMOVE s.label;

// 6k. Drop the GDS in-memory graph when done
CALL gds.graph.drop('coinvest');

// 6l. (Optional) Remove the temporary CO_INVESTS_WITH relationships
MATCH (s1:Shareholder)-[r:CO_INVESTS_WITH]-(s2:Shareholder)
DELETE r;

// ---------------------------------------------------------------------------
// 7. Industry distribution (if Industry nodes were loaded)
// ---------------------------------------------------------------------------

// 5a. Most common industry classifications
MATCH (ind:Industry)<-[:HAS_INDUSTRY]-(:Company)
RETURN ind.code AS anzsic_code,
       ind.description AS description,
       count(*) AS companies
ORDER BY companies DESC
LIMIT 20;

// ---------------------------------------------------------------------------
// 8. Node classification with embeddings + node features
// ---------------------------------------------------------------------------

// 8a. Compute additional node features
MATCH (s:Shareholder)-[:HOLDS_SHARES_IN]->(c:Company)
WITH s, count(DISTINCT c) AS cnt
SET s.company_count = cnt;

MATCH (s:Shareholder)-[:CO_INVESTS_WITH]-()
WITH s, count(*) AS cnt
SET s.co_investor_count = cnt;

CALL gds.pageRank.write('coinvest', {
  relationshipWeightProperty: 'weight',
  writeProperty: 'page_rank'
});

// 8b. Node2Vec embedding + features combined classification (α=0.7)
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
RETURN predicted AS class, count(*) AS count ORDER BY count DESC;

// 8c. FastRP embedding + features combined classification (α=0.7)
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
RETURN predicted AS class, count(*) AS count ORDER BY count DESC;

// 8d. Set best_label = FastRP + features (best performing config)
MATCH (s:Shareholder)
WHERE s.fastrp_combined_label IS NOT NULL AND s.label IS NULL
SET s.best_label = s.fastrp_combined_label;

// 8e. Compare predictions across methods for specific test entities
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
       s.fastrp_label AS fastrp_only,
       s.fastrp_combined_label AS fastrp_feat
ORDER BY s.name;

// 8f. Find nearest labeled seeds for a given entity (FastRP)
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
LIMIT 10;

// 8g. Best label distribution summary
MATCH (s:Shareholder) WHERE s.best_label IS NOT NULL
RETURN s.best_label AS class,
       count(*) AS count,
       round(100.0 * count(*) / 9257, 1) AS pct
ORDER BY count DESC;

// ---------------------------------------------------------------------------
// 9. Entity Resolution — unify Shareholder + Director identities
// ---------------------------------------------------------------------------
// The Shareholder CSV has double spaces in names ("Gurpreet  SINGH"),
// Director CSV uses single spaces ("Gurpreet SINGH").
// Steps: normalize → add name_key for fuzzy matching → unified queries.

// 9a. Add normalized_name (collapse whitespace) — must be a separate pass
//     because SET evaluates all RHS against the pre-SET state of the node,
//     so subsequent assignments cannot reference the freshly-set value.
MATCH (s:Shareholder)
SET s.normalized_name = trim(apoc.text.replace(s.name, '\\s+', ' '));

MATCH (d:Director)
SET d.normalized_name = trim(apoc.text.replace(d.name, '\\s+', ' '));

// 9b. Now that normalized_name exists, set person_id and is_person
MATCH (s:Shareholder)
SET s.person_id = s.normalized_name,
    s.is_person = CASE WHEN s.normalized_name =~ '.*[a-z].*' THEN true ELSE false END;

MATCH (d:Director)
SET d.person_id = d.normalized_name,
    d.is_person = CASE WHEN d.normalized_name =~ '.*[a-z].*' THEN true ELSE false END;

// 9c. Create indexes for fast lookups
CREATE INDEX IF NOT EXISTS FOR (s:Shareholder) ON (s.normalized_name);
CREATE INDEX IF NOT EXISTS FOR (d:Director) ON (d.normalized_name);
CREATE INDEX IF NOT EXISTS FOR (s:Shareholder) ON (s.person_id);
CREATE INDEX IF NOT EXISTS FOR (d:Director) ON (d.person_id);

// 9d. Add name_key for fuzzy matching (firstWord + lastWord)
// Handles middle-name variants: "Melissa CLARK" == "Melissa Alice CLARK"
MATCH (s:Shareholder)
SET s.name_key = toUpper(split(s.normalized_name, ' ')[0]) + toUpper(split(s.normalized_name, ' ')[-1]);

MATCH (d:Director)
SET d.name_key = toUpper(split(d.normalized_name, ' ')[0]) + toUpper(split(d.normalized_name, ' ')[-1]);

CREATE INDEX IF NOT EXISTS FOR (s:Shareholder) ON (s.name_key);
CREATE INDEX IF NOT EXISTS FOR (d:Director) ON (d.name_key);

// 9d. Entity resolution summary stats
MATCH (s:Shareholder {is_person: true})
WITH count(DISTINCT s.person_id) AS unique_sh_persons
MATCH (d:Director {is_person: true})
WITH unique_sh_persons, count(DISTINCT d.person_id) AS unique_dir_persons
MATCH (s:Shareholder {is_person: true})
WHERE EXISTS { MATCH (d:Director) WHERE d.normalized_name = s.normalized_name }
WITH unique_sh_persons, unique_dir_persons, count(DISTINCT s) AS with_both
MATCH (d:Director {is_person: true})
WHERE NOT EXISTS { MATCH (s:Shareholder) WHERE s.normalized_name = d.normalized_name }
RETURN unique_sh_persons AS shareholders,
       unique_dir_persons AS directors,
       with_both AS persons_with_both_roles,
       count(DISTINCT d) AS directors_only;

// 9e. Top unified economic actors (shareholder + director combined)
MATCH (s:Shareholder)
WHERE s.is_person = true AND s.company_count >= 20
OPTIONAL MATCH (d:Director {normalized_name: s.normalized_name})-[:DIRECTS]->(c:Company)
WITH s.normalized_name AS name,
     s.company_count AS sh_companies,
     count(DISTINCT c) AS dir_companies
WHERE dir_companies > 0
RETURN name, sh_companies, dir_companies,
       sh_companies + dir_companies AS total_activities
ORDER BY total_activities DESC
LIMIT 20;

// 9f. Find all activity for a specific person
MATCH (s:Shareholder {normalized_name: 'Gurpreet SINGH'})-[:HOLDS_SHARES_IN]->(c:Company)
OPTIONAL MATCH (d:Director {normalized_name: 'Gurpreet SINGH'})-[:DIRECTS]->(c)
RETURN c.name AS company,
       CASE WHEN s IS NOT NULL THEN 'SHAREHOLDER' ELSE '' END AS share,
       CASE WHEN d IS NOT NULL THEN 'DIRECTOR' ELSE '' END AS direct
LIMIT 20;

// 9g. Fuzzy match candidates (name_key match but NOT normalized_name match)
MATCH (s:Shareholder)
WHERE NOT EXISTS {
    MATCH (d:Director) WHERE d.normalized_name = s.normalized_name
  }
  AND EXISTS {
    MATCH (d:Director) WHERE d.name_key = s.name_key
  }
  AND s.is_person = true AND s.company_count >= 5
RETURN count(*) AS fuzzy_candidates;

// 9h. Persons with large shareholder-minus-director gap (possible nominee pattern)
MATCH (s:Shareholder)
WHERE s.is_person = true AND s.company_count >= 10
OPTIONAL MATCH (d:Director {normalized_name: s.normalized_name})-[:DIRECTS]->(c:Company)
WITH s.normalized_name AS name,
     s.company_count AS sh,
     count(DISTINCT c) AS dir,
     s.company_count - count(DISTINCT c) AS gap
WHERE gap >= 50
RETURN name, sh, dir, gap
ORDER BY gap DESC
LIMIT 15;

// ---------------------------------------------------------------------------
// 10. Trigram similarity matching for fuzzy entity resolution
// ---------------------------------------------------------------------------
// Pre-compute trigrams (3-char substrings) for all names.
// Jaccard similarity on trigram sets handles middle-name variants,
// spelling differences, and hyphenation better than name_key alone.
// Thresholds: >=0.65 high, >=0.55 medium, >=0.5 low confidence.

// 10a. Pre-compute trigrams (one-time setup)
MATCH (n)
WHERE (n:Shareholder OR n:Director) AND n.normalized_name IS NOT NULL
WITH n, toLower(n.normalized_name) AS clean
WITH n, '  ' + clean + ' ' AS padded
SET n.trigrams = [i IN range(0, size(padded) - 3) | substring(padded, i, 3)];

// 10b. Find trigram matches for unmatched Shareholder → Director
MATCH (s:Shareholder)
WHERE NOT EXISTS {
    MATCH (d:Director) WHERE d.normalized_name = s.normalized_name
  }
  AND s.is_person = true AND s.company_count >= 3
  AND s.name_key IS NOT NULL AND s.trigrams IS NOT NULL
WITH s
MATCH (d:Director)
WHERE d.name_key = s.name_key AND d.is_person = true AND d.trigrams IS NOT NULL
WITH s, d,
     size([x IN s.trigrams WHERE x IN d.trigrams]) * 1.0
       / (size(s.trigrams) + size(d.trigrams) - size([x IN s.trigrams WHERE x IN d.trigrams])) AS jaccard
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
    END;

// 10c. Same for unmatched Director → Shareholder
MATCH (d:Director)
WHERE NOT EXISTS {
    MATCH (s:Shareholder) WHERE s.normalized_name = d.normalized_name
  }
  AND d.is_person = true AND d.name_key IS NOT NULL AND d.trigrams IS NOT NULL
WITH d
MATCH (s:Shareholder)
WHERE s.name_key = d.name_key AND s.is_person = true AND s.trigrams IS NOT NULL
WITH d, s,
     size([x IN d.trigrams WHERE x IN s.trigrams]) * 1.0
       / (size(d.trigrams) + size(s.trigrams) - size([x IN d.trigrams WHERE x IN s.trigrams])) AS jaccard
WHERE jaccard >= 0.55
WITH d, s.normalized_name AS match_name, jaccard
ORDER BY jaccard DESC
WITH d, collect(match_name)[0] AS best_match, max(jaccard) AS best_score
SET d.trigram_match = best_match,
    d.trigram_score = best_score,
    d.match_confidence = CASE
      WHEN best_score >= 0.65 THEN 'high'
      WHEN best_score >= 0.55 THEN 'medium'
    END;

// 10d. Trigram similarity query—find the top-k closest names for a given person
WITH 'Teresa Ann MCCAHILL' AS query
WITH toLower(trim(apoc.text.replace(query, '\\s+', ' '))) AS clean
WITH '  ' + clean + ' ' AS padded
WITH [i IN range(0, size(padded)-3) | substring(padded,i,3)] AS q_trigrams
MATCH (s:Shareholder)
WHERE s.is_person = true AND s.trigrams IS NOT NULL
WITH s, q_trigrams,
     size([x IN q_trigrams WHERE x IN s.trigrams]) * 1.0
       / (size(q_trigrams) + size(s.trigrams) - size([x IN q_trigrams WHERE x IN s.trigrams])) AS jaccard
WHERE jaccard >= 0.4
RETURN s.normalized_name AS name, round(jaccard, 3) AS similarity
ORDER BY similarity DESC
LIMIT 10;

// 10e. Create Person nodes and SAME_AS relationships for trigram-matched pairs
// Person is the canonical identity (keyed by the Director's normalized_name).
MATCH (s:Shareholder) WHERE s.trigram_match IS NOT NULL
WITH DISTINCT s.trigram_match AS canonical
MERGE (p:Person {person_id: canonical});

MATCH (d:Director) WHERE d.trigram_match IS NOT NULL
  AND NOT EXISTS { MATCH (p:Person {person_id: d.trigram_match}) }
WITH DISTINCT d.trigram_match AS canonical
MERGE (p:Person {person_id: canonical});

CREATE INDEX person_id IF NOT EXISTS FOR (p:Person) ON (p.person_id);

// Create SAME_AS edges from variant names to canonical Person
MATCH (s:Shareholder)
WHERE s.trigram_match IS NOT NULL
MATCH (p:Person {person_id: s.trigram_match})
CREATE (s)-[:SAME_AS {score: s.trigram_score, confidence: s.match_confidence}]->(p);

MATCH (d:Director)
WHERE d.trigram_match IS NOT NULL AND NOT EXISTS { MATCH (d)-[:SAME_AS]->(:Person) }
MATCH (p:Person {person_id: d.trigram_match})
CREATE (d)-[:SAME_AS {score: d.trigram_score, confidence: d.match_confidence}]->(p);

// 10f. Traverse: from any variant name find canonical Person + all their activity
MATCH (s:Shareholder {person_id: 'Teresa Ann MCCAHILL'})
OPTIONAL MATCH (s)-[:SAME_AS]->(p:Person)
WITH coalesce(p.person_id, s.person_id) AS canonical
MATCH (all_sh:Shareholder)
WHERE all_sh.person_id = canonical
   OR (all_sh.trigram_match IS NOT NULL AND all_sh.trigram_match = canonical)
OPTIONAL MATCH (d:Director {person_id: canonical})
RETURN canonical AS person,
       collect(DISTINCT all_sh.person_id) AS shareholder_names,
       collect(DISTINCT d.person_id) AS director_names;

// 10g. Entity resolution final stats
MATCH (s:Shareholder)
WITH count(s) AS sh_total,
     count(CASE WHEN EXISTS { MATCH (d:Director) WHERE d.normalized_name = s.normalized_name } THEN 1 END) AS sh_exact_match,
     count(s.trigram_match) AS sh_trigram_match
MATCH (d:Director)
WITH sh_total, sh_exact_match, sh_trigram_match,
     count(d) AS dir_total,
     count(CASE WHEN EXISTS { MATCH (s:Shareholder) WHERE s.normalized_name = d.normalized_name } THEN 1 END) AS dir_exact_match,
     count(d.trigram_match) AS dir_trigram_match
MATCH (p:Person)
RETURN sh_total, sh_exact_match, sh_trigram_match,
       dir_total, dir_exact_match, dir_trigram_match,
       count(p) AS person_nodes,
       count(()-[:SAME_AS]->(p)) AS same_as_relationships;

// 10h. Verify trigram matches by company overlap (disambiguation)
// Names alone give ~87% false positives. Company overlap confirms same person.
MATCH (s:Shareholder)-[r:SAME_AS]->(p:Person)
WHERE s.trigram_score >= 0.55
MATCH (d:Director {person_id: p.person_id})
OPTIONAL MATCH (s)-[:HOLDS_SHARES_IN]->(c:Company)<-[:DIRECTS]-(d)
WITH r, count(DISTINCT c) AS overlap
SET r.company_overlap = overlap,
    r.verified = CASE WHEN overlap >= 1 THEN true ELSE false END;

MATCH (s:Shareholder)-[r:SAME_AS]->(p:Person)
RETURN r.verified AS verified,
       round(avg(r.score), 3) AS avg_trigram_score,
       count(*) AS count,
       collect(s.normalized_name + ' ↔ ' + p.person_id)[0..3] AS examples
ORDER BY verified;

// 10i. People with verified name variants (after disambiguation)
MATCH (s:Shareholder)-[r:SAME_AS {verified: true}]->(p:Person)
WITH p, collect(DISTINCT s.normalized_name) AS variants
MATCH (d:Director {person_id: p.person_id})
WITH p.person_id AS canonical, variants + [p.person_id] AS all_names
UNWIND all_names AS name
WITH canonical, collect(DISTINCT name) AS unique_names
RETURN canonical, size(unique_names) AS verified_variants, unique_names
ORDER BY verified_variants DESC
LIMIT 15;
