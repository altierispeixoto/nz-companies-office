WITH monthly AS (
    SELECT
        nzbn,
        shareholder_name,
        snapshot_month,
        sum(number_of_shares) AS shares,
        max(sh_type) AS sh_type,
        bool_or(is_person) AS is_person,
        max(name_key) AS name_key,
        bool_or(extensive_shareholding) AS extensive_shareholding,
        max(sh_status) AS sh_status
    FROM read_parquet($silver_glob, hive_partitioning = false)
    GROUP BY nzbn, shareholder_name, snapshot_month
),
latest AS (
    SELECT *
    FROM monthly
    QUALIFY row_number() OVER (PARTITION BY nzbn, shareholder_name ORDER BY snapshot_month DESC) = 1
),
company_totals AS (
    SELECT nzbn, sum(shares) AS total_shares
    FROM latest
    GROUP BY nzbn
)
SELECT
    l.nzbn,
    l.shareholder_name,
    l.shares,
    l.sh_type,
    l.is_person,
    l.name_key,
    l.extensive_shareholding,
    l.sh_status,
    l.snapshot_month AS as_of_snapshot_month,
    ct.total_shares,
    CASE WHEN ct.total_shares > 0 THEN l.shares::DOUBLE / ct.total_shares * 100.0 ELSE 0.0 END AS share_percentage,
    (ct.total_shares > 0 AND l.shares::DOUBLE / ct.total_shares > 0.5) AS is_majority
FROM latest AS l
JOIN company_totals AS ct ON l.nzbn = ct.nzbn
