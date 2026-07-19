LOAD CSV WITH HEADERS FROM "file:///companies/companies_business_industry_classification.csv" AS row
CALL (row) {
    WITH row
    WHERE row.INDUSTRY_CLASSIFICATION_CODE =~ '^[A-Z]\\d{6}$'
    MATCH (c:Company {nzbn: row.NZBN})
    MERGE (ind:Industry {code: row.INDUSTRY_CLASSIFICATION_CODE})
    SET ind.description = row.INDUSTRY_CLASSIFICATION_DESCRIPTION
    WITH ind, c
    MERGE (c)-[:HAS_INDUSTRY]->(ind)
} IN TRANSACTIONS OF 5000 ROWS;
