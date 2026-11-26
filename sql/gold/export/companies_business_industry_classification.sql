SELECT
    nzbn AS NZBN,
    coalesce(strftime(start_date, '%Y-%m-%d'), '') AS START_DATE,
    industry_code AS INDUSTRY_CLASSIFICATION_CODE,
    industry_description AS INDUSTRY_CLASSIFICATION_DESCRIPTION
FROM read_parquet($input_path, hive_partitioning = false)
