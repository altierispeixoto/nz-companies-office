LOAD CSV WITH HEADERS FROM "file:///companies/companies_website.csv" AS row
CALL (row) {
    MATCH (c:Company {nzbn: row.NZBN})
    SET c.website = row.WEBSITE
} IN TRANSACTIONS OF 5000 ROWS;

LOAD CSV WITH HEADERS FROM "file:///companies/companies_gst.csv" AS row
CALL (row) {
    MATCH (c:Company {nzbn: row.NZBN})
    SET c.gst_number = row.GST_NUMBER
} IN TRANSACTIONS OF 5000 ROWS;

LOAD CSV WITH HEADERS FROM "file:///companies/companies_abn.csv" AS row
CALL (row) {
    MATCH (c:Company {nzbn: row.NZBN})
    SET c.abn = row.ABN
} IN TRANSACTIONS OF 5000 ROWS;

LOAD CSV WITH HEADERS FROM "file:///companies/maori_business_identifier.csv" AS row
CALL (row) {
    MATCH (c:Company {nzbn: row.NZBN})
    SET c.maori_business_identifier = row.IDENTIFYING_FACTOR
} IN TRANSACTIONS OF 5000 ROWS;
