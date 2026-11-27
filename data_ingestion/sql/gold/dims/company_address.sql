SELECT
    nzbn,
    address_type,
    md5(street || '|' || city || '|' || country) AS address_key,
    start_date AS since,
    snapshot_month AS as_of_snapshot_month
FROM read_parquet($silver_glob, hive_partitioning = false)
QUALIFY row_number() OVER (PARTITION BY nzbn, address_type ORDER BY snapshot_month DESC) = 1
