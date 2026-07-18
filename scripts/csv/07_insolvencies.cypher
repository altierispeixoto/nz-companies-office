LOAD CSV WITH HEADERS FROM "file:///companies/companies_insolvency.csv" AS row
CALL (row) {
    MATCH (c:Company {nzbn: row.NZBN})
    MERGE (i:Insolvency {
        type: row.INSOLVENCY_TYPE,
        appointment_type: coalesce(row.APPOINTMENT_TYPE, ""),
        appointee: trim(
            coalesce(row.APPOINTEE_FIRST_NAME, "") + " " +
            coalesce(row.APPOINTEE_MIDDLE_NAMES, "") + " " +
            coalesce(row.APPOINTEE_LAST_NAME, "")
        )
    })
    SET i.organisation = row.ORGANISATION
    WITH i, c, row
    MERGE (c)-[r:HAS_INSOLVENCY]->(i)
    SET r.appointed_on = CASE
            WHEN row.APPOINTMENT_DATE <> "" AND size(row.APPOINTMENT_DATE) = 10
            THEN date(
                substring(row.APPOINTMENT_DATE, 6, 4) + "-" +
                substring(row.APPOINTMENT_DATE, 3, 2) + "-" +
                substring(row.APPOINTMENT_DATE, 0, 2)
            )
            ELSE null
        END,
        r.vacated_on = CASE
            WHEN row.APPOINTMENT_VACATED_DATE <> "" AND size(row.APPOINTMENT_VACATED_DATE) = 10
            THEN date(
                substring(row.APPOINTMENT_VACATED_DATE, 6, 4) + "-" +
                substring(row.APPOINTMENT_VACATED_DATE, 3, 2) + "-" +
                substring(row.APPOINTMENT_VACATED_DATE, 0, 2)
            )
            ELSE null
        END,
        r.resolution_of_solvency = CASE
            WHEN trim(coalesce(row.RESSOLUTION_OF_SOLVENCY, "")) <> ""
            THEN trim(row.RESSOLUTION_OF_SOLVENCY)
            ELSE null
        END
} IN TRANSACTIONS OF 5000 ROWS;
