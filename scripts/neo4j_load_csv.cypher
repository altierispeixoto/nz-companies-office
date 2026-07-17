// Step 0: Drop GDS in-memory graphs + ML models + all data, then create indexes
// GDS in-memory graphs persist across restarts and must be dropped explicitly
CALL gds.graph.list() YIELD graphName
WITH graphName
CALL gds.graph.drop(graphName, false) YIELD graphName AS dropped
RETURN count(dropped) AS graphs_dropped;

CALL apoc.periodic.iterate(
    "MATCH (n) RETURN n",
    "DETACH DELETE n",
    {batchSize: 50000, parallel: false, retries: 0}
);

// Create all MERGE-key indexes upfront so each MERGE uses an index lookup
// (without indexes, MERGE does a full node scan that gets slower with every row)

CREATE INDEX company_nzbn IF NOT EXISTS FOR (c:Company) ON (c.nzbn);
CREATE INDEX company_number_idx IF NOT EXISTS FOR (c:Company) ON (c.company_number);
CREATE INDEX director_name_idx IF NOT EXISTS FOR (d:Director) ON (d.name);
CREATE INDEX shareholder_name_idx IF NOT EXISTS FOR (s:Shareholder) ON (s.name);
CREATE INDEX address_physical_idx IF NOT EXISTS FOR (a:Address) ON (a.street, a.city, a.country);
CREATE INDEX industry_code_idx IF NOT EXISTS FOR (ind:Industry) ON (ind.code);
CREATE INDEX trading_name_idx IF NOT EXISTS FOR (t:TradingName) ON (t.name);
CREATE INDEX insolvency_idx IF NOT EXISTS FOR (i:Insolvency) ON (i.type, i.appointment_type, i.appointee);
CREATE INDEX trading_area_idx IF NOT EXISTS FOR (ta:TradingArea) ON (ta.name);
CREATE INDEX company_name_idx IF NOT EXISTS FOR (c:Company) ON (c.name);
CREATE INDEX shareholder_surname_idx IF NOT EXISTS FOR (s:Shareholder) ON (s.surname);
CREATE INDEX director_last_name_idx IF NOT EXISTS FOR (d:Director) ON (d.last_name);

// Step 1: Load Company nodes (1.81M rows)
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

// Step 2: Load Director nodes + :DIRECTS relationships (1.17M rows)
//         Appointment date + ASIC flag stored on the relationship (edge attributes)
LOAD CSV WITH HEADERS FROM "file:///companies/companies_director.csv" AS row
CALL (row) {
    MATCH (c:Company {nzbn: row.NZBN})
    WITH row, c,
        trim(
            CASE WHEN trim(coalesce(row.FIRST_NAME, "")) <> "" THEN trim(row.FIRST_NAME) + " " ELSE "" END +
            CASE WHEN trim(coalesce(row.MIDDLE_NAMES, "")) <> "" THEN trim(row.MIDDLE_NAMES) + " " ELSE "" END +
            coalesce(row.LAST_NAME, "")
        ) AS raw_name
    WITH row, c, raw_name,
        CASE WHEN raw_name <> "" THEN raw_name ELSE row.ENTITY_NAME END AS director_name
    MERGE (d:Director {name: director_name})
    WITH d, c, row
    MERGE (d)-[r:DIRECTS]->(c)
    SET r.appointed_on = CASE
            WHEN row.START_DATE <> "" AND size(row.START_DATE) = 10
            THEN date(
                substring(row.START_DATE, 6, 4) + "-" +
                substring(row.START_DATE, 3, 2) + "-" +
                substring(row.START_DATE, 0, 2)
            )
            ELSE null
        END,
        r.asic_dir_yn = CASE WHEN trim(row.ASIC_DIR_YN) = "Y" THEN true ELSE false END
} IN TRANSACTIONS OF 5000 ROWS;

// Step 3: Load Shareholder nodes + :HOLDS_SHARES_IN relationships (1.58M rows)
//         Share count, extensive shareholding, start date, status, parcel/assignment IDs on the edge;
//         type on the node; address stored as Address node
LOAD CSV WITH HEADERS FROM "file:///companies/companies_shareholder.csv" AS row
CALL (row) {
    MATCH (c:Company {nzbn: row.NZBN})
    MERGE (s:Shareholder {name: row.SH_NAME})
    SET s.sh_type = CASE
            WHEN trim(coalesce(row.SH_TYPE, "")) <> "" THEN trim(row.SH_TYPE)
            ELSE null
        END
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

// Step 4a: Load Registered Office Address nodes (755K rows)
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

// Step 4b: Load Address for Service nodes (755K rows)
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

// Step 5: Load Industry nodes + :HAS_INDUSTRY relationships (664K rows)
LOAD CSV WITH HEADERS FROM "file:///companies/companies_business_industry_classification.csv" AS row
CALL (row) {
    MATCH (c:Company {nzbn: row.NZBN})
    MERGE (ind:Industry {code: row.INDUSTRY_CLASSIFICATION_CODE})
    SET ind.description = row.INDUSTRY_CLASSIFICATION_DESCRIPTION
    WITH ind, c
    MERGE (c)-[:HAS_INDUSTRY]->(ind)
} IN TRANSACTIONS OF 5000 ROWS;

// Step 6: Load TradingName nodes + :TRADES_AS relationships (346K rows)
LOAD CSV WITH HEADERS FROM "file:///companies/companies_trading_name.csv" AS row
CALL (row) {
    MATCH (c:Company {nzbn: row.NZBN})
    MERGE (t:TradingName {name: row.TRADING_NAME})
    SET t.start_date = CASE
            WHEN row.START_DATE <> "" AND size(row.START_DATE) = 10
            THEN date(
                substring(row.START_DATE, 6, 4) + "-" +
                substring(row.START_DATE, 3, 2) + "-" +
                substring(row.START_DATE, 0, 2)
            )
            ELSE null
        END
    WITH t, c
    MERGE (c)-[:TRADES_AS]->(t)
} IN TRANSACTIONS OF 5000 ROWS;

// Step 7: Load Insolvency nodes + :HAS_INSOLVENCY relationships (108K rows)
//         Appointment/vacated dates stored on the relationship (edge attributes)
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

// Step 8: Add properties from remaining CSVs (website, GST, ABN, Maori business)
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

// Step 9: Load TradingArea nodes + :TRADES_IN relationships
LOAD CSV WITH HEADERS FROM "file:///companies/companies_trading_area.csv" AS row
CALL (row) {
    MATCH (c:Company {nzbn: row.NZBN})
    MERGE (ta:TradingArea {name: trim(row.TRADING_AREA)})
    WITH ta, c
    MERGE (c)-[:TRADES_IN]->(ta)
} IN TRANSACTIONS OF 5000 ROWS;

// Step 4c: Load Public Address nodes (320K rows)
LOAD CSV WITH HEADERS FROM "file:///companies/companies_public_address.csv" AS row
CALL (row) {
    MATCH (c:Company {nzbn: row.NZBN})
    WITH c, row,
        coalesce(row.ADDRESS_3, "") AS city_3,
        coalesce(row.ADDRESS_4, "") AS city_4
    WITH c, row,
        CASE
            WHEN trim(city_3) <> "" THEN trim(city_3)
            WHEN trim(city_4) <> "" THEN trim(city_4)
            ELSE null
        END AS city
    WITH c, row, city
    WHERE coalesce(row.ADDRESS_1, "") <> "" OR city IS NOT NULL OR coalesce(row.ADDRESS_COUNTRY, "") <> ""
    MERGE (a:Address {
        street: coalesce(row.ADDRESS_1, ""),
        city: coalesce(city, ""),
        country: coalesce(row.ADDRESS_COUNTRY, "")
    })
    SET a.suburb = CASE WHEN trim(coalesce(row.ADDRESS_2, "")) <> "" THEN trim(row.ADDRESS_2) ELSE null END,
        a.postcode = CASE WHEN trim(coalesce(row.ADDRESS_POSTCODE, "")) <> "" THEN trim(row.ADDRESS_POSTCODE) ELSE null END
    WITH a, c, row
    MERGE (c)-[r:HAS_ADDRESS]->(a)
    SET r.address_type = CASE
            WHEN row.TYPE = "Registered Office" THEN "REGISTERED_OFFICE"
            WHEN row.TYPE = "Address for Service" THEN "SERVICE"
            ELSE "PUBLIC"
        END,
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

// Step 10: Link corporate shareholders to their Company nodes
// Shareholder sh_type = "Shareholder Company" means this shareholder
// IS a known company on the register. Connect them via name match.
CALL apoc.periodic.iterate(
    'MATCH (s:Shareholder)
     WHERE s.sh_type = "Shareholder Company"
     RETURN s',
    'WITH s
     MATCH (c:Company {name: s.name})
     MERGE (s)-[:IS]->(c)',
    {batchSize: 5000, parallel: false, retries: 0}
);
