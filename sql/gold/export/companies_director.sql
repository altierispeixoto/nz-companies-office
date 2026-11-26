SELECT
    nzbn AS NZBN,
    director_name AS DIRECTOR_NAME,
    coalesce(strftime(appointed_on, '%Y-%m-%d'), '') AS START_DATE,
    CASE WHEN asic_dir_yn THEN 'true' ELSE 'false' END AS ASIC_DIR_YN,
    CASE WHEN is_person THEN 'true' ELSE 'false' END AS IS_PERSON,
    name_key AS NAME_KEY
FROM read_parquet($input_path, hive_partitioning = false)
