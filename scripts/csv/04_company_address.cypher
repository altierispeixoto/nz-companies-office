LOAD CSV WITH HEADERS FROM "file:///companies/companies_company_address.csv" AS row
CALL (row) {
    MATCH (c:Company {nzbn: row.NZBN})
    MERGE (a:Address {street: row.STREET, city: row.CITY, country: row.COUNTRY})
    SET a.suburb = CASE WHEN row.SUBURB <> "" THEN row.SUBURB ELSE null END,
        a.postcode = CASE WHEN row.POSTCODE <> "" THEN row.POSTCODE ELSE null END
    WITH a, c, row
    MERGE (c)-[r:HAS_ADDRESS]->(a)
    SET r.address_type = row.ADDRESS_TYPE,
        r.since = CASE WHEN row.START_DATE <> "" THEN date(row.START_DATE) ELSE null END
} IN TRANSACTIONS OF 5000 ROWS;
