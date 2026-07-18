LOAD CSV WITH HEADERS FROM "file:///companies/companies_shareholder.csv" AS row
CALL (row) {
    MATCH (c:Company {nzbn: row.NZBN})
    MERGE (s:Shareholder {name: row.SH_NAME})
    SET s.sh_type = CASE
            WHEN trim(coalesce(row.SH_TYPE, "")) <> "" THEN trim(row.SH_TYPE)
            ELSE null
        END
    SET s.normalized_name = trim(apoc.text.replace(s.name, '\\s+', ' '))
    SET s.person_id = s.normalized_name,
        s.is_person = CASE WHEN s.normalized_name =~ '.*[a-z].*' THEN true ELSE false END,
        s.name_key = toUpper(split(s.normalized_name, ' ')[0]) + toUpper(split(s.normalized_name, ' ')[-1])
    WITH s, c, row,
        coalesce(row.SH_ADDRESS_3, "") AS city_3,
        coalesce(row.SH_ADDRESS_4, "") AS city_4
    WITH s, c, row,
        CASE
            WHEN trim(city_3) <> "" THEN trim(city_3)
            WHEN trim(city_4) <> "" THEN trim(city_4)
            ELSE null
        END AS city
    WITH s, c, row, city
    WHERE coalesce(row.SH_ADDRESS_1, "") <> "" OR city IS NOT NULL OR coalesce(row.SH_ADDRESS_COUNTRY, "") <> ""
    MERGE (a:Address {
        street: coalesce(row.SH_ADDRESS_1, ""),
        city: coalesce(city, ""),
        country: coalesce(row.SH_ADDRESS_COUNTRY, "")
    })
    SET a.care_of = CASE WHEN trim(coalesce(row.SH_ADDRESS_CARE_OF, "")) <> "" THEN trim(row.SH_ADDRESS_CARE_OF) ELSE null END,
        a.suburb = CASE WHEN trim(coalesce(row.SH_ADDRESS_2, "")) <> "" THEN trim(row.SH_ADDRESS_2) ELSE null END,
        a.postcode = CASE WHEN trim(coalesce(row.SH_ADDRESS_POSTCODE, "")) <> "" THEN trim(row.SH_ADDRESS_POSTCODE) ELSE null END,
        a.paf_id = CASE WHEN trim(coalesce(row.SH_ADDRESS_PAF_ID, "")) <> "" THEN trim(row.SH_ADDRESS_PAF_ID) ELSE null END
    WITH s, a, c, row
    MERGE (s)-[:HAS_ADDRESS]->(a)
    WITH s, c, row
    MERGE (s)-[r:HOLDS_SHARES_IN]->(c)
    SET r.shares = CASE
            WHEN row.NUMBER_OF_SHARES <> "" AND row.NUMBER_OF_SHARES IS NOT NULL
            THEN toInteger(row.NUMBER_OF_SHARES)
            ELSE 0
        END,
        r.extensive_shareholding = CASE WHEN trim(row.SH_EXTENSIVE_SHAREHOLDING_YN) = "Y" THEN true ELSE false END,
        r.start_date = CASE
            WHEN row.START_DATE <> "" AND size(row.START_DATE) = 10
            THEN date(
                substring(row.START_DATE, 6, 4) + "-" +
                substring(row.START_DATE, 3, 2) + "-" +
                substring(row.START_DATE, 0, 2)
            )
            ELSE null
        END,
        r.sh_status = CASE WHEN trim(coalesce(row.SH_STATUS, "")) <> "" THEN trim(row.SH_STATUS) ELSE null END,
        r.parcel_id = CASE WHEN coalesce(row.PARCEL_IDENTIFIER, "") <> "" THEN row.PARCEL_IDENTIFIER ELSE null END,
        r.assignment_id = CASE WHEN coalesce(row.ASSIGNMENT_IDENTIFIER, "") <> "" THEN row.ASSIGNMENT_IDENTIFIER ELSE null END
} IN TRANSACTIONS OF 5000 ROWS;
