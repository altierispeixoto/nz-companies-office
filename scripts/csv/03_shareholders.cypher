LOAD CSV WITH HEADERS FROM "file:///companies/companies_shareholder.csv" AS row
CALL (row) {
    MATCH (c:Company {nzbn: row.NZBN})
    MERGE (s:Shareholder {name: row.SHAREHOLDER_NAME})
    SET s.sh_type = CASE WHEN row.SH_TYPE <> "" THEN row.SH_TYPE ELSE null END,
        s.normalized_name = s.name,
        s.person_id = s.name,
        s.is_person = (row.IS_PERSON = "true"),
        s.name_key = row.NAME_KEY
    WITH s, c, row
    MERGE (s)-[r:HOLDS_SHARES_IN]->(c)
    SET r.shares = toInteger(row.NUMBER_OF_SHARES),
        r.extensive_shareholding = (row.EXTENSIVE_SHAREHOLDING = "true"),
        r.start_date = CASE WHEN row.START_DATE <> "" THEN date(row.START_DATE) ELSE null END,
        r.sh_status = CASE WHEN row.SH_STATUS <> "" THEN row.SH_STATUS ELSE null END,
        r.parcel_id = CASE WHEN row.PARCEL_ID <> "" THEN row.PARCEL_ID ELSE null END,
        r.assignment_id = CASE WHEN row.ASSIGNMENT_ID <> "" THEN row.ASSIGNMENT_ID ELSE null END,
        r.share_percentage = toFloat(row.SHARE_PERCENTAGE),
        r.is_majority = (row.IS_MAJORITY = "true")
    WITH s, row
    WHERE coalesce(row.ADDRESS_STREET, "") <> "" OR coalesce(row.ADDRESS_CITY, "") <> ""
        OR coalesce(row.ADDRESS_COUNTRY, "") <> ""
    MERGE (a:Address {
        street: coalesce(row.ADDRESS_STREET, ""),
        city: coalesce(row.ADDRESS_CITY, ""),
        country: coalesce(row.ADDRESS_COUNTRY, "")
    })
    SET a.care_of = CASE WHEN row.ADDRESS_CARE_OF <> "" THEN row.ADDRESS_CARE_OF ELSE null END,
        a.suburb = CASE WHEN row.ADDRESS_SUBURB <> "" THEN row.ADDRESS_SUBURB ELSE null END,
        a.postcode = CASE WHEN row.ADDRESS_POSTCODE <> "" THEN row.ADDRESS_POSTCODE ELSE null END
    WITH s, a
    MERGE (s)-[:HAS_ADDRESS]->(a)
} IN TRANSACTIONS OF 5000 ROWS;
