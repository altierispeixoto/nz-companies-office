WITH base AS (
    SELECT
        NZBN AS nzbn,
        ENTITY_NAME AS company_name,
        CASE WHEN START_DATE != '' THEN strptime(START_DATE, '%d/%m/%Y')::DATE END AS start_date,
        (trim(ASIC_DIR_YN) = 'Y') AS asic_dir_yn,
        CASE WHEN coalesce(ACN, '') != '' THEN ACN END AS acn,
        CASE WHEN coalesce(ASIC_COMPANY_NAME, '') != '' THEN ASIC_COMPANY_NAME END AS asic_company_name,
        trim(
            CASE WHEN trim(coalesce(FIRST_NAME, '')) != '' THEN trim(FIRST_NAME) || ' ' ELSE '' END ||
            CASE WHEN trim(coalesce(MIDDLE_NAMES, '')) != '' THEN trim(MIDDLE_NAMES) || ' ' ELSE '' END ||
            coalesce(LAST_NAME, '')
        ) AS raw_name,
        ENTITY_NAME,
        NZBN AS src_nzbn
    FROM read_parquet($input_path, hive_partitioning = false)
),
named AS (
    SELECT
        *,
        CASE WHEN raw_name != '' THEN raw_name ELSE ENTITY_NAME END AS director_name
    FROM base
)
SELECT
    nzbn,
    company_name,
    start_date,
    asic_dir_yn,
    acn,
    asic_company_name,
    director_name,
    trim(regexp_replace(director_name, '\s+', ' ', 'g')) AS normalized_name,
    regexp_matches(trim(regexp_replace(director_name, '\s+', ' ', 'g')), '[a-z]') AS is_person,
    upper(list_extract(string_split(trim(regexp_replace(director_name, '\s+', ' ', 'g')), ' '), 1))
        || upper(list_extract(string_split(trim(regexp_replace(director_name, '\s+', ' ', 'g')), ' '), -1)) AS name_key,
    $month AS snapshot_month
FROM named
QUALIFY row_number() OVER (PARTITION BY nzbn, director_name, start_date ORDER BY start_date) = 1
