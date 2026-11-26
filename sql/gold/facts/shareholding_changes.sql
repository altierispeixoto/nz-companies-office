WITH curr AS (
    SELECT nzbn, shareholder_name, sum(number_of_shares) AS shares
    FROM read_parquet($current_path, hive_partitioning = false)
    GROUP BY nzbn, shareholder_name
),
prev AS (
    SELECT nzbn, shareholder_name, sum(number_of_shares) AS shares
    FROM read_parquet($previous_path, hive_partitioning = false)
    GROUP BY nzbn, shareholder_name
)
SELECT
    coalesce(curr.nzbn, prev.nzbn) AS nzbn,
    coalesce(curr.shareholder_name, prev.shareholder_name) AS shareholder_name,
    $month AS snapshot_month,
    CASE
        WHEN prev.shares IS NULL THEN 'NEW'
        WHEN curr.shares IS NULL THEN 'EXITED'
        WHEN curr.shares > prev.shares THEN 'INCREASED'
        ELSE 'DECREASED'
    END AS change_type,
    prev.shares AS shares_before,
    curr.shares AS shares_after
FROM curr
FULL OUTER JOIN prev ON curr.nzbn = prev.nzbn AND curr.shareholder_name = prev.shareholder_name
WHERE curr.shares IS DISTINCT FROM prev.shares
