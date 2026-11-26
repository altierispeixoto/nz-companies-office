LOAD CSV WITH HEADERS FROM "file:///companies/companies_director.csv" AS row
CALL (row) {
    MATCH (c:Company {nzbn: row.NZBN})
    MERGE (d:Director {name: row.DIRECTOR_NAME})
    SET d.normalized_name = d.name,
        d.person_id = d.name,
        d.is_person = (row.IS_PERSON = "true"),
        d.name_key = row.NAME_KEY
    WITH d, c, row
    MERGE (d)-[r:DIRECTS]->(c)
    SET r.appointed_on = CASE WHEN row.START_DATE <> "" THEN date(row.START_DATE) ELSE null END,
        r.asic_dir_yn = (row.ASIC_DIR_YN = "true")
} IN TRANSACTIONS OF 5000 ROWS;
