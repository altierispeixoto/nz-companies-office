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
CREATE INDEX address_key_idx IF NOT EXISTS FOR (a:Address) ON (a.address_type, a.street, a.city, a.country);
CREATE INDEX industry_code_idx IF NOT EXISTS FOR (ind:Industry) ON (ind.code);
CREATE INDEX trading_name_idx IF NOT EXISTS FOR (t:TradingName) ON (t.name);
CREATE INDEX insolvency_idx IF NOT EXISTS FOR (i:Insolvency) ON (i.type, i.appointment_type, i.appointee);
CREATE INDEX trading_area_idx IF NOT EXISTS FOR (ta:TradingArea) ON (ta.name);
CREATE INDEX company_name_idx IF NOT EXISTS FOR (c:Company) ON (c.name);
CREATE INDEX shareholder_surname_idx IF NOT EXISTS FOR (s:Shareholder) ON (s.surname);
CREATE INDEX director_last_name_idx IF NOT EXISTS FOR (d:Director) ON (d.last_name);

// Step 1: Load Company nodes (1.81M rows)
CALL () {
    LOAD CSV WITH HEADERS FROM "file:///companies/companies_core_data.csv" AS row
    MERGE (c:Company {company_number: row.COMPANY_IDENTIFIER})
    SET c.nzbn = row.NZBN,
        c.name = row.ENTITY_NAME,
        c.entity_type = row.ENTITY_TYPE,
        c.status = CASE
            WHEN toLower(trim(row.ENTITY_STATUS)) = "registered" THEN "REGISTERED"
            ELSE "REMOVED"
        END,
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
CALL () {
    LOAD CSV WITH HEADERS FROM "file:///companies/companies_director.csv" AS row
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
//         type + address on the node (address is last-row-wins for shareholder)
CALL () {
    LOAD CSV WITH HEADERS FROM "file:///companies/companies_shareholder.csv" AS row
    MATCH (c:Company {nzbn: row.NZBN})
    MERGE (s:Shareholder {name: row.SH_NAME})
    SET s.sh_type = CASE
            WHEN trim(coalesce(row.SH_TYPE, "")) <> "" THEN trim(row.SH_TYPE)
            ELSE null
        END,
        s.sh_address_care_of = CASE WHEN trim(coalesce(row.SH_ADDRESS_CARE_OF, "")) <> "" THEN trim(row.SH_ADDRESS_CARE_OF) ELSE null END,
        s.sh_address_1 = CASE WHEN trim(coalesce(row.SH_ADDRESS_1, "")) <> "" THEN trim(row.SH_ADDRESS_1) ELSE null END,
        s.sh_address_2 = CASE WHEN trim(coalesce(row.SH_ADDRESS_2, "")) <> "" THEN trim(row.SH_ADDRESS_2) ELSE null END,
        s.sh_address_3 = CASE WHEN trim(coalesce(row.SH_ADDRESS_3, "")) <> "" THEN trim(row.SH_ADDRESS_3) ELSE null END,
        s.sh_address_4 = CASE WHEN trim(coalesce(row.SH_ADDRESS_4, "")) <> "" THEN trim(row.SH_ADDRESS_4) ELSE null END,
        s.sh_address_postcode = CASE WHEN trim(coalesce(row.SH_ADDRESS_POSTCODE, "")) <> "" THEN trim(row.SH_ADDRESS_POSTCODE) ELSE null END,
        s.sh_address_country = CASE WHEN trim(coalesce(row.SH_ADDRESS_COUNTRY, "")) <> "" THEN trim(row.SH_ADDRESS_COUNTRY) ELSE null END,
        s.sh_address_paf_id = CASE WHEN trim(coalesce(row.SH_ADDRESS_PAF_ID, "")) <> "" THEN trim(row.SH_ADDRESS_PAF_ID) ELSE null END
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
CALL () {
    LOAD CSV WITH HEADERS FROM "file:///companies/companies_registered_office_address.csv" AS row
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
    MERGE (a:Address {
        address_type: "REGISTERED_OFFICE",
        street: coalesce(row.REGISTERED_OFFICE_ADDRESS_1, ""),
        city: coalesce(city, ""),
        country: coalesce(row.REGISTERED_OFFICE_ADDRESS_COUNTRY, "")
    })
    SET a.suburb = CASE WHEN trim(coalesce(row.REGISTERED_OFFICE_ADDRESS_2, "")) <> "" THEN trim(row.REGISTERED_OFFICE_ADDRESS_2) ELSE null END,
        a.postcode = CASE WHEN trim(coalesce(row.REGISTERED_OFFICE_ADDRESS_POSTCODE, "")) <> "" THEN trim(row.REGISTERED_OFFICE_ADDRESS_POSTCODE) ELSE null END
    WITH a, c, row
    MERGE (c)-[r:HAS_ADDRESS]->(a)
    SET r.since = CASE
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
CALL () {
    LOAD CSV WITH HEADERS FROM "file:///companies/companies_address_for_service.csv" AS row
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
    MERGE (a:Address {
        address_type: "SERVICE",
        street: coalesce(row.ADDRESS_FOR_SERVICE_1, ""),
        city: coalesce(city, ""),
        country: coalesce(row.ADDRESS_FOR_SERVICE_COUNTRY, "")
    })
    SET a.suburb = CASE WHEN trim(coalesce(row.ADDRESS_FOR_SERVICE_2, "")) <> "" THEN trim(row.ADDRESS_FOR_SERVICE_2) ELSE null END,
        a.postcode = CASE WHEN trim(coalesce(row.ADDRESS_FOR_SERVICE_POSTCODE, "")) <> "" THEN trim(row.ADDRESS_FOR_SERVICE_POSTCODE) ELSE null END
    WITH a, c, row
    MERGE (c)-[r:HAS_ADDRESS]->(a)
    SET r.since = CASE
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
CALL () {
    LOAD CSV WITH HEADERS FROM "file:///companies/companies_business_industry_classification.csv" AS row
    MATCH (c:Company {nzbn: row.NZBN})
    MERGE (ind:Industry {code: row.INDUSTRY_CLASSIFICATION_CODE})
    SET ind.description = row.INDUSTRY_CLASSIFICATION_DESCRIPTION
    WITH ind, c
    MERGE (c)-[:HAS_INDUSTRY]->(ind)
} IN TRANSACTIONS OF 5000 ROWS;

// Step 6: Load TradingName nodes + :TRADES_AS relationships (346K rows)
CALL () {
    LOAD CSV WITH HEADERS FROM "file:///companies/companies_trading_name.csv" AS row
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
CALL () {
    LOAD CSV WITH HEADERS FROM "file:///companies/companies_insolvency.csv" AS row
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
CALL () {
    LOAD CSV WITH HEADERS FROM "file:///companies/companies_website.csv" AS row
    MATCH (c:Company {nzbn: row.NZBN})
    SET c.website = row.WEBSITE
} IN TRANSACTIONS OF 5000 ROWS;

CALL () {
    LOAD CSV WITH HEADERS FROM "file:///companies/companies_gst.csv" AS row
    MATCH (c:Company {nzbn: row.NZBN})
    SET c.gst_number = row.GST_NUMBER
} IN TRANSACTIONS OF 5000 ROWS;

CALL () {
    LOAD CSV WITH HEADERS FROM "file:///companies/companies_abn.csv" AS row
    MATCH (c:Company {nzbn: row.NZBN})
    SET c.abn = row.ABN
} IN TRANSACTIONS OF 5000 ROWS;

CALL () {
    LOAD CSV WITH HEADERS FROM "file:///companies/maori_business_identifier.csv" AS row
    MATCH (c:Company {nzbn: row.NZBN})
    SET c.maori_business_identifier = row.IDENTIFYING_FACTOR
} IN TRANSACTIONS OF 5000 ROWS;

// Step 9: Load TradingArea nodes + :TRADES_IN relationships
CALL () {
    LOAD CSV WITH HEADERS FROM "file:///companies/companies_trading_area.csv" AS row
    MATCH (c:Company {nzbn: row.NZBN})
    MERGE (ta:TradingArea {name: trim(row.TRADING_AREA)})
    WITH ta, c
    MERGE (c)-[:TRADES_IN]->(ta)
} IN TRANSACTIONS OF 5000 ROWS;

// Step 4c: Load Public Address nodes (320K rows)
CALL () {
    LOAD CSV WITH HEADERS FROM "file:///companies/companies_public_address.csv" AS row
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
    MERGE (a:Address {
        address_type: CASE
            WHEN row.TYPE = "Registered Office" THEN "REGISTERED_OFFICE"
            WHEN row.TYPE = "Address for Service" THEN "SERVICE"
            ELSE "PUBLIC"
        END,
        street: coalesce(row.ADDRESS_1, ""),
        city: coalesce(city, ""),
        country: coalesce(row.ADDRESS_COUNTRY, "")
    })
    SET a.suburb = CASE WHEN trim(coalesce(row.ADDRESS_2, "")) <> "" THEN trim(row.ADDRESS_2) ELSE null END,
        a.postcode = CASE WHEN trim(coalesce(row.ADDRESS_POSTCODE, "")) <> "" THEN trim(row.ADDRESS_POSTCODE) ELSE null END
    WITH a, c, row
    MERGE (c)-[r:HAS_ADDRESS]->(a)
    SET r.since = CASE
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
CALL () {
    MATCH (s:Shareholder)
    WHERE s.sh_type = "Shareholder Company"
    MATCH (c:Company {name: s.name})
    MERGE (s)-[:IS]->(c)
} IN TRANSACTIONS OF 5000 ROWS;

// Step 11: Extract surname for individual shareholders
// Handles "First Last" and "Last, First" name formats.
MATCH (s:Shareholder)
WHERE s.sh_type <> "Shareholder Company" OR s.sh_type IS NULL
WITH s,
    CASE
        WHEN s.name CONTAINS ", " THEN trim(split(s.name, ",")[0])
        ELSE last(split(s.name, " "))
    END AS raw_surname
WHERE raw_surname IS NOT NULL AND size(raw_surname) > 1
SET s.surname = raw_surname;

// Step 12: Link individual co-investors sharing a surname
// Only links when both shareholders invest in the same company,
// making it far more likely they are relatives (vs. same-surname coincidence).
CALL apoc.periodic.iterate(
    'MATCH (s1:Shareholder)-[:HOLDS_SHARES_IN]->(c:Company)<-[:HOLDS_SHARES_IN]-(s2:Shareholder)
     WHERE (s1.sh_type <> "Shareholder Company" OR s1.sh_type IS NULL)
       AND (s2.sh_type <> "Shareholder Company" OR s2.sh_type IS NULL)
       AND s1.surname IS NOT NULL AND s2.surname = s1.surname
       AND id(s1) < id(s2)
     RETURN DISTINCT s1, s2',
    'MERGE (s1)-[:RELATED_TO]->(s2)',
    {batchSize: 5000, parallel: false, retries: 0}
);

// Step 13a: Extract last_name on Director nodes
MATCH (d:Director)
WITH d, last(split(d.name, " ")) AS raw_last
WHERE raw_last IS NOT NULL AND size(raw_last) > 1
SET d.last_name = raw_last;

// Step 13b: Extract first_initial on individual Shareholder nodes
MATCH (s:Shareholder)
WHERE s.sh_type <> "Shareholder Company" OR s.sh_type IS NULL
WITH s,
    CASE
        WHEN s.name CONTAINS ", " THEN trim(split(s.name, ",")[1])
        ELSE trim(split(s.name, " ")[0])
    END AS first_word
WHERE first_word IS NOT NULL AND size(first_word) > 0
SET s.first_initial = substring(first_word, 0, 1);

// Step 13c: Link individual shareholders to directors in the same company
// when names match (same surname + same first initial = likely same person).
CALL apoc.periodic.iterate(
    'MATCH (s:Shareholder)-[:HOLDS_SHARES_IN]->(c:Company)<-[:DIRECTS]-(d:Director)
     WHERE (s.sh_type <> "Shareholder Company" OR s.sh_type IS NULL)
       AND s.surname IS NOT NULL AND s.first_initial IS NOT NULL
       AND d.last_name IS NOT NULL
       AND s.surname = d.last_name
       AND s.first_initial = substring(d.name, 0, 1)
     RETURN DISTINCT s, d',
    'MERGE (s)-[:IS_INVESTOR_DIRECTOR]->(d)',
    {batchSize: 5000, parallel: false, retries: 0}
);
