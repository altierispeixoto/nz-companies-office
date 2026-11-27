SELECT
    NZBN AS nzbn,
    CASE WHEN START_DATE != '' THEN strptime(START_DATE, '%d/%m/%Y')::DATE END AS start_date,
    INDUSTRY_CLASSIFICATION_CODE AS industry_code,
    INDUSTRY_CLASSIFICATION_DESCRIPTION AS industry_description,
    $month AS snapshot_month
FROM read_parquet($input_path, hive_partitioning = false)
WHERE regexp_matches(INDUSTRY_CLASSIFICATION_CODE, '^[A-Z]\d{6}$')
QUALIFY row_number() OVER (PARTITION BY NZBN, INDUSTRY_CLASSIFICATION_CODE ORDER BY START_DATE) = 1
