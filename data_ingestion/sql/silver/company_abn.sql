SELECT
    NZBN AS nzbn,
    CASE WHEN coalesce(ABN, '') != '' THEN ABN END AS abn,
    $month AS snapshot_month
FROM read_parquet($input_path, hive_partitioning = false)
QUALIFY row_number() OVER (PARTITION BY NZBN ORDER BY ABN) = 1
