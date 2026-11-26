SELECT
    nzbn,
    trading_area,
    start_date,
    snapshot_month AS as_of_snapshot_month
FROM read_parquet($silver_glob, hive_partitioning = false)
QUALIFY row_number() OVER (PARTITION BY nzbn, trading_area ORDER BY snapshot_month DESC) = 1
