CALL apoc.periodic.iterate(
    'MATCH (s:Shareholder)
     WHERE s.sh_type = "Shareholder Company"
     RETURN s',
    'WITH s
     MATCH (c:Company {name: s.name})
     MERGE (s)-[:IS]->(c)',
    {batchSize: 5000, parallel: false, retries: 0}
);
