LOAD CSV WITH HEADERS FROM "file:///companies/companies_core_data.csv" AS row
CALL (row) {
    MERGE (c:Company {company_number: row.COMPANY_IDENTIFIER})
    SET c.nzbn = row.NZBN,
        c.name = row.ENTITY_NAME,
        c.entity_type = row.ENTITY_TYPE,
        c.status = row.ENTITY_STATUS,
        c.incorporation_date = CASE
            WHEN row.REGISTRATION_DATE <> "" AND size(row.REGISTRATION_DATE) = 10
            THEN date(
                substring(row.REGISTRATION_DATE, 6, 4) + "-" +
                substring(row.REGISTRATION_DATE, 3, 2) + "-" +
                substring(row.REGISTRATION_DATE, 0, 2)
            )
            ELSE null
        END,
        c.removal_date = CASE
            WHEN row.REMOVAL_DATE <> "" AND size(row.REMOVAL_DATE) = 10
            THEN date(
                substring(row.REMOVAL_DATE, 6, 4) + "-" +
                substring(row.REMOVAL_DATE, 3, 2) + "-" +
                substring(row.REMOVAL_DATE, 0, 2)
            )
            ELSE null
        END
} IN TRANSACTIONS OF 5000 ROWS;
