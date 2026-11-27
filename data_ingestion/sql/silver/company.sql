SELECT
    NZBN AS nzbn,
    COMPANY_IDENTIFIER AS company_number,
    ENTITY_NAME AS entity_name,
    ENTITY_TYPE AS entity_type,
    ENTITY_STATUS AS entity_status,
    CASE WHEN REGISTRATION_DATE != '' THEN strptime(REGISTRATION_DATE, '%d/%m/%Y')::DATE END AS incorporation_date,
    CASE WHEN REMOVAL_DATE != '' THEN strptime(REMOVAL_DATE, '%d/%m/%Y')::DATE END AS removal_date,
    $month AS snapshot_month,
    coalesce(regexp_matches(NZBN, '^[0-9]{13}$'), false) AS is_valid_nzbn_format
FROM read_parquet($input_path, hive_partitioning = false)
QUALIFY row_number() OVER (PARTITION BY NZBN ORDER BY COMPANY_IDENTIFIER) = 1
