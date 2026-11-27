SELECT
    curr.nzbn AS nzbn,
    $month AS snapshot_month,
    prev.entity_status AS previous_status,
    curr.entity_status AS new_status,
    prev.snapshot_month AS previous_snapshot_month,
    current_timestamp AS detected_at
FROM read_parquet($current_path, hive_partitioning = false) AS curr
INNER JOIN read_parquet($previous_path, hive_partitioning = false) AS prev
    ON curr.nzbn = prev.nzbn
WHERE curr.entity_status IS DISTINCT FROM prev.entity_status
