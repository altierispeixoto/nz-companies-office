SELECT
    nzbn,
    director_name,
    start_date AS appointed_on,
    asic_dir_yn,
    is_person,
    name_key,
    snapshot_month AS as_of_snapshot_month
FROM read_parquet($silver_glob, hive_partitioning = false)
QUALIFY row_number() OVER (PARTITION BY nzbn, director_name ORDER BY snapshot_month DESC) = 1
