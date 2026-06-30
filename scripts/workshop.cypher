
call db.schema.visualization()

MATCH (n:Company) RETURN n LIMIT 25;

MATCH (s:Shareholder)-[sh:HOLDS_SHARES_IN {sh_status:"active"}]->(c:Company)
where  c.status <> 'REMOVED'
   and c.name = "AUROR LIMITED"
RETURN *


MATCH (s:Shareholder)-[sh:HOLDS_SHARES_IN {sh_status:"active"}]->(c:Company)-[ha:HAS_ADDRESS ]->(a:Address)
where  c.status <> 'REMOVED'
   and c.name = "AUROR LIMITED"
   and a.address_type = "REGISTERED_OFFICE"
RETURN s.name as shareholder,
       sh.shares as shares,
       sh.start_date as start_date,
       c.name as name,
       a.country,
       a.street,
       a.suburb
order by shares desc


MATCH (auror:Company)
WHERE auror.name = 'AUROR LIMITED'
MATCH (s:Shareholder)-[auror_edge:HOLDS_SHARES_IN]->(auror)
MATCH (s)-[other_edge:HOLDS_SHARES_IN]->(other:Company)-[:HAS_INDUSTRY]->(i:Industry)
WHERE other <> auror
  and s.sh_type  = "Shareholder Company"
RETURN s.name AS shareholder,
       COLLECT(DISTINCT other.name) as companies,
       COLLECT(DISTINCT i.description) as industries,
       COUNT { (s)-[:HOLDS_SHARES_IN]->() } AS total_companies,
       COUNT  (distinct i.code ) AS total_industries
ORDER BY total_companies DESC


MATCH (d:Director)-[:DIRECTS]->(c:Company)<-[:HOLDS_SHARES_IN]-(s:Shareholder)
WHERE d.name = s.name
RETURN d.name AS person,
       count(DISTINCT c) AS overlap_companies
ORDER BY overlap_companies DESC
LIMIT 20;


MATCH (s1:Shareholder)-[:HOLDS_SHARES_IN]->(c:Company)<-[:HOLDS_SHARES_IN]-(s2:Shareholder)
where elementId(s1) < elementId(s2)
RETURN s1.name AS shareholder_1,
       s2.name  as shareholder_2,
       count( distinct c.name) as co_investors
order by  co_investors desc
LIMIT 20;


MATCH (s1:Shareholder)-[:HOLDS_SHARES_IN]->(c:Company)<-[:HOLDS_SHARES_IN]-(s2:Shareholder)
WHERE elementId(s1) < elementId(s2)
WITH s1, s2, count(DISTINCT c) AS weight
WHERE weight >= 5
MERGE (s1)-[r:CO_INVESTS_WITH]-(s2)
SET r.weight = weight;


// CLUSTERING

CALL gds.louvain.stream('coinvest', { relationshipWeightProperty: 'weight' })
YIELD nodeId, communityId
RETURN communityId, count(nodeId) as nodes order by nodes desc


CALL gds.louvain.stream('coinvest', { relationshipWeightProperty: 'weight' })
YIELD nodeId, communityId, intermediateCommunityIds
WITH gds.util.asNode(nodeId).name AS shareholder, communityId
RETURN communityId,
       count(*) AS members,
       collect(shareholder) AS shareholders
ORDER BY members DESC
LIMIT 30;
