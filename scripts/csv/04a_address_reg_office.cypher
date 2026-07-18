LOAD CSV WITH HEADERS FROM "file:///companies/companies_registered_office_address.csv" AS row
CALL (row) {
    MATCH (c:Company {nzbn: row.NZBN})
    WITH c, row,
        coalesce(row.REGISTERED_OFFICE_ADDRESS_3, "") AS city_3,
        coalesce(row.REGISTERED_OFFICE_ADDRESS_4, "") AS city_4
    WITH c, row,
        CASE
            WHEN trim(city_3) <> "" THEN trim(city_3)
            WHEN trim(city_4) <> "" THEN trim(city_4)
            ELSE null
        END AS city
    WITH c, row, city
    WHERE coalesce(row.REGISTERED_OFFICE_ADDRESS_1, "") <> "" OR city IS NOT NULL OR coalesce(row.REGISTERED_OFFICE_ADDRESS_COUNTRY, "") <> ""
    MERGE (a:Address {
        street: coalesce(row.REGISTERED_OFFICE_ADDRESS_1, ""),
        city: coalesce(city, ""),
        country: coalesce(row.REGISTERED_OFFICE_ADDRESS_COUNTRY, "")
    })
    SET a.suburb = CASE WHEN trim(coalesce(row.REGISTERED_OFFICE_ADDRESS_2, "")) <> "" THEN trim(row.REGISTERED_OFFICE_ADDRESS_2) ELSE null END,
        a.postcode = CASE WHEN trim(coalesce(row.REGISTERED_OFFICE_ADDRESS_POSTCODE, "")) <> "" THEN trim(row.REGISTERED_OFFICE_ADDRESS_POSTCODE) ELSE null END
    WITH a, c, row
    MERGE (c)-[r:HAS_ADDRESS]->(a)
    SET r.address_type = "REGISTERED_OFFICE",
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
