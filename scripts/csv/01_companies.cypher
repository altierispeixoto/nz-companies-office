LOAD CSV WITH HEADERS FROM "file:///companies/companies_core_data.csv" AS row
CALL (row) {
    MERGE (c:Company {company_number: row.COMPANY_IDENTIFIER})
    SET c.nzbn = row.NZBN,
        c.name = row.ENTITY_NAME,
        c.entity_type = row.ENTITY_TYPE,
        c.status = row.ENTITY_STATUS,
        c.incorporation_date = CASE WHEN row.INCORPORATION_DATE <> "" THEN date(row.INCORPORATION_DATE) ELSE null END,
        c.removal_date = CASE WHEN row.REMOVAL_DATE <> "" THEN date(row.REMOVAL_DATE) ELSE null END
} IN TRANSACTIONS OF 5000 ROWS;
