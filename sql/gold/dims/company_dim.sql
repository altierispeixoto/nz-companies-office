SELECT
    nzbn,
    company_number,
    entity_name,
    entity_type,
    entity_status,
    incorporation_date,
    removal_date,
    snapshot_month AS as_of_snapshot_month
FROM read_parquet($silver_glob, hive_partitioning = false)
QUALIFY row_number() OVER (PARTITION BY nzbn ORDER BY snapshot_month DESC) = 1
