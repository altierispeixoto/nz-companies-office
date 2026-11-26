SELECT
    nzbn,
    industry_code,
    industry_description,
    start_date,
    snapshot_month AS as_of_snapshot_month
FROM read_parquet($silver_glob, hive_partitioning = false)
QUALIFY row_number() OVER (PARTITION BY nzbn, industry_code ORDER BY snapshot_month DESC) = 1
