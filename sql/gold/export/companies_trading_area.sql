SELECT
    nzbn AS NZBN,
    trading_area AS TRADING_AREA
FROM read_parquet($input_path, hive_partitioning = false)
