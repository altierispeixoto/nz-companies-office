SELECT
    nzbn AS NZBN,
    insolvency_type AS INSOLVENCY_TYPE,
    coalesce(appointment_type, '') AS APPOINTMENT_TYPE,
    appointee AS APPOINTEE,
    coalesce(organisation, '') AS ORGANISATION,
    coalesce(strftime(appointment_date, '%Y-%m-%d'), '') AS APPOINTMENT_DATE,
    coalesce(strftime(appointment_vacated_date, '%Y-%m-%d'), '') AS APPOINTMENT_VACATED_DATE,
    coalesce(resolution_of_solvency, '') AS RESOLUTION_OF_SOLVENCY
FROM read_parquet($input_path, hive_partitioning = false)
