SELECT
    nzbn,
    insolvency_type,
    appointment_type,
    appointee,
    organisation,
    appointment_date,
    appointment_vacated_date,
    resolution_of_solvency,
    snapshot_month AS as_of_snapshot_month
FROM read_parquet($silver_glob, hive_partitioning = false)
QUALIFY row_number() OVER (
    PARTITION BY nzbn, insolvency_type, appointment_type, appointment_date
    ORDER BY snapshot_month DESC
) = 1
