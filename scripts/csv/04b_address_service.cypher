LOAD CSV WITH HEADERS FROM "file:///companies/companies_address_for_service.csv" AS row
CALL (row) {
    MATCH (c:Company {nzbn: row.NZBN})
    WITH c, row,
        coalesce(row.ADDRESS_FOR_SERVICE_3, "") AS city_3,
        coalesce(row.ADDRESS_FOR_SERVICE_4, "") AS city_4
    WITH c, row,
        CASE
            WHEN trim(city_3) <> "" THEN trim(city_3)
            WHEN trim(city_4) <> "" THEN trim(city_4)
            ELSE null
        END AS city
    WITH c, row, city
    WHERE coalesce(row.ADDRESS_FOR_SERVICE_1, "") <> "" OR city IS NOT NULL OR coalesce(row.ADDRESS_FOR_SERVICE_COUNTRY, "") <> ""
    MERGE (a:Address {
        street: coalesce(row.ADDRESS_FOR_SERVICE_1, ""),
        city: coalesce(city, ""),
        country: coalesce(row.ADDRESS_FOR_SERVICE_COUNTRY, "")
    })
    SET a.suburb = CASE WHEN trim(coalesce(row.ADDRESS_FOR_SERVICE_2, "")) <> "" THEN trim(row.ADDRESS_FOR_SERVICE_2) ELSE null END,
        a.postcode = CASE WHEN trim(coalesce(row.ADDRESS_FOR_SERVICE_POSTCODE, "")) <> "" THEN trim(row.ADDRESS_FOR_SERVICE_POSTCODE) ELSE null END
    WITH a, c, row
    MERGE (c)-[r:HAS_ADDRESS]->(a)
    SET r.address_type = "SERVICE",
        r.since = CASE
            WHEN row.START_DATE <> "" AND size(row.START_DATE) = 10
            THEN date(
                substring(row.START_DATE, 6, 4) + "-" +
                substring(row.START_DATE, 3, 2) + "-" +
                substring(row.START_DATE, 0, 2)
            )
            ELSE null
        END
} IN TRANSACTIONS OF 5000 ROWS;
