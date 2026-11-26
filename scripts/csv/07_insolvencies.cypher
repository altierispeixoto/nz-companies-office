LOAD CSV WITH HEADERS FROM "file:///companies/companies_insolvency.csv" AS row
CALL (row) {
    MATCH (c:Company {nzbn: row.NZBN})
    MERGE (i:Insolvency {
        type: row.INSOLVENCY_TYPE,
        appointment_type: row.APPOINTMENT_TYPE,
        appointee: row.APPOINTEE
    })
    SET i.organisation = row.ORGANISATION
    WITH i, c, row
    MERGE (c)-[r:HAS_INSOLVENCY]->(i)
    SET r.appointed_on = CASE WHEN row.APPOINTMENT_DATE <> "" THEN date(row.APPOINTMENT_DATE) ELSE null END,
        r.vacated_on = CASE
            WHEN row.APPOINTMENT_VACATED_DATE <> "" THEN date(row.APPOINTMENT_VACATED_DATE) ELSE null
        END,
        r.resolution_of_solvency = CASE WHEN row.RESOLUTION_OF_SOLVENCY <> "" THEN row.RESOLUTION_OF_SOLVENCY ELSE null END
} IN TRANSACTIONS OF 5000 ROWS;
