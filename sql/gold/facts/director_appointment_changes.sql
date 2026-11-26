WITH curr AS (
    SELECT DISTINCT nzbn, director_name FROM read_parquet($current_path, hive_partitioning = false)
),
prev AS (
    SELECT DISTINCT nzbn, director_name FROM read_parquet($previous_path, hive_partitioning = false)
)
SELECT
    coalesce(curr.nzbn, prev.nzbn) AS nzbn,
    coalesce(curr.director_name, prev.director_name) AS director_name,
    $month AS snapshot_month,
    CASE WHEN prev.nzbn IS NULL THEN 'APPOINTED' ELSE 'RESIGNED' END AS change_type
FROM curr
FULL OUTER JOIN prev ON curr.nzbn = prev.nzbn AND curr.director_name = prev.director_name
WHERE curr.nzbn IS NULL OR prev.nzbn IS NULL
