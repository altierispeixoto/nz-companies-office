SELECT
    NZBN AS nzbn,
    INSOLVENCY_TYPE AS insolvency_type,
    coalesce(APPOINTMENT_TYPE, '') AS appointment_type,
    trim(
        coalesce(APPOINTEE_FIRST_NAME, '') || ' ' ||
        coalesce(APPOINTEE_MIDDLE_NAMES, '') || ' ' ||
        coalesce(APPOINTEE_LAST_NAME, '')
    ) AS appointee,
    ORGANISATION AS organisation,
    CASE WHEN APPOINTMENT_DATE != '' THEN strptime(APPOINTMENT_DATE, '%d/%m/%Y')::DATE END AS appointment_date,
    CASE
        WHEN APPOINTMENT_VACATED_DATE != '' THEN strptime(APPOINTMENT_VACATED_DATE, '%d/%m/%Y')::DATE
    END AS appointment_vacated_date,
    CASE
        WHEN trim(coalesce(RESSOLUTION_OF_SOLVENCY, '')) != '' THEN trim(RESSOLUTION_OF_SOLVENCY)
    END AS resolution_of_solvency,
    $month AS snapshot_month
FROM read_parquet($input_path, hive_partitioning = false)
QUALIFY row_number() OVER (
    PARTITION BY NZBN, INSOLVENCY_TYPE, APPOINTMENT_TYPE, APPOINTMENT_DATE
    ORDER BY APPOINTMENT_DATE
) = 1
