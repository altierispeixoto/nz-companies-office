SELECT
    NZBN AS nzbn,
    CASE WHEN START_DATE != '' THEN strptime(START_DATE, '%d/%m/%Y')::DATE END AS start_date,
    TRADING_NAME AS trading_name,
    $month AS snapshot_month
FROM read_parquet($input_path, hive_partitioning = false)
QUALIFY row_number() OVER (PARTITION BY NZBN, TRADING_NAME ORDER BY START_DATE) = 1
