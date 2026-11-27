SELECT
    nzbn AS NZBN,
    trading_name AS TRADING_NAME,
    coalesce(strftime(start_date, '%Y-%m-%d'), '') AS START_DATE
FROM read_parquet($input_path, hive_partitioning = false)
