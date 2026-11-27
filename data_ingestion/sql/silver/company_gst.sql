SELECT
    NZBN AS nzbn,
    CASE WHEN START_DATE != '' THEN strptime(START_DATE, '%d/%m/%Y')::DATE END AS start_date,
    CASE WHEN coalesce(GST_NUMBER, '') != '' THEN GST_NUMBER END AS gst_number,
    $month AS snapshot_month
FROM read_parquet($input_path, hive_partitioning = false)
QUALIFY row_number() OVER (PARTITION BY NZBN ORDER BY START_DATE DESC) = 1
