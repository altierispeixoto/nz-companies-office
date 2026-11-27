SELECT
    NZBN AS nzbn,
    CASE WHEN START_DATE != '' THEN strptime(START_DATE, '%d/%m/%Y')::DATE END AS start_date,
    trim(TRADING_AREA) AS trading_area,
    $month AS snapshot_month
FROM read_parquet($input_path, hive_partitioning = false)
QUALIFY row_number() OVER (PARTITION BY NZBN, trim(TRADING_AREA) ORDER BY START_DATE) = 1
