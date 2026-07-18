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
    SET d.normalized_name = trim(apoc.text.replace(d.name, '\\s+', ' '))
    SET d.person_id = d.normalized_name,
        d.is_person = CASE WHEN d.normalized_name =~ '.*[a-z].*' THEN true ELSE false END,
        d.name_key = toUpper(split(d.normalized_name, ' ')[0]) + toUpper(split(d.normalized_name, ' ')[-1])
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
