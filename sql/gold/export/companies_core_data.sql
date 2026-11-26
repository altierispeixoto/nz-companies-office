SELECT
    nzbn AS NZBN,
    company_number AS COMPANY_IDENTIFIER,
    entity_name AS ENTITY_NAME,
    incorporation_date AS INCORPORATION_DATE,
    removal_date AS REMOVAL_DATE,
    entity_type AS ENTITY_TYPE,
    entity_status AS ENTITY_STATUS
FROM read_parquet($input_path, hive_partitioning = false)
