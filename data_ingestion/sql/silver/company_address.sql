WITH reg_office AS (
    SELECT
        NZBN AS nzbn,
        'REGISTERED_OFFICE' AS address_type,
        CASE WHEN START_DATE != '' THEN strptime(START_DATE, '%d/%m/%Y')::DATE END AS start_date,
        CASE WHEN trim(coalesce(REGISTERED_OFFICE_ADDRESS_CARE_OF, '')) != ''
            THEN trim(REGISTERED_OFFICE_ADDRESS_CARE_OF) END AS care_of,
        CASE WHEN trim(coalesce(REGISTERED_OFFICE_ADDRESS_PAF_ID, '')) != ''
            THEN trim(REGISTERED_OFFICE_ADDRESS_PAF_ID) END AS paf_id,
        coalesce(REGISTERED_OFFICE_ADDRESS_1, '') AS street,
        CASE WHEN trim(coalesce(REGISTERED_OFFICE_ADDRESS_2, '')) != ''
            THEN trim(REGISTERED_OFFICE_ADDRESS_2) END AS suburb,
        coalesce(
            CASE WHEN trim(coalesce(REGISTERED_OFFICE_ADDRESS_3, '')) != '' THEN trim(REGISTERED_OFFICE_ADDRESS_3) END,
            CASE WHEN trim(coalesce(REGISTERED_OFFICE_ADDRESS_4, '')) != '' THEN trim(REGISTERED_OFFICE_ADDRESS_4) END,
            ''
        ) AS city,
        CASE WHEN trim(coalesce(REGISTERED_OFFICE_ADDRESS_POSTCODE, '')) != ''
            THEN trim(REGISTERED_OFFICE_ADDRESS_POSTCODE) END AS postcode,
        coalesce(REGISTERED_OFFICE_ADDRESS_COUNTRY, '') AS country
    FROM read_parquet($input_reg_office, hive_partitioning = false)
),
service AS (
    SELECT
        NZBN AS nzbn,
        'SERVICE' AS address_type,
        CASE WHEN START_DATE != '' THEN strptime(START_DATE, '%d/%m/%Y')::DATE END AS start_date,
        CASE WHEN trim(coalesce(ADDRESS_FOR_SERVICE_CARE_OF, '')) != ''
            THEN trim(ADDRESS_FOR_SERVICE_CARE_OF) END AS care_of,
        CASE WHEN trim(coalesce(ADDRESS_FOR_SERVICE_PAF_ID, '')) != ''
            THEN trim(ADDRESS_FOR_SERVICE_PAF_ID) END AS paf_id,
        coalesce(ADDRESS_FOR_SERVICE_1, '') AS street,
        CASE WHEN trim(coalesce(ADDRESS_FOR_SERVICE_2, '')) != '' THEN trim(ADDRESS_FOR_SERVICE_2) END AS suburb,
        coalesce(
            CASE WHEN trim(coalesce(ADDRESS_FOR_SERVICE_3, '')) != '' THEN trim(ADDRESS_FOR_SERVICE_3) END,
            CASE WHEN trim(coalesce(ADDRESS_FOR_SERVICE_4, '')) != '' THEN trim(ADDRESS_FOR_SERVICE_4) END,
            ''
        ) AS city,
        CASE WHEN trim(coalesce(ADDRESS_FOR_SERVICE_POSTCODE, '')) != ''
            THEN trim(ADDRESS_FOR_SERVICE_POSTCODE) END AS postcode,
        coalesce(ADDRESS_FOR_SERVICE_COUNTRY, '') AS country
    FROM read_parquet($input_service, hive_partitioning = false)
),
public_addr AS (
    SELECT
        NZBN AS nzbn,
        CASE
            WHEN TYPE = 'Registered Office' THEN 'REGISTERED_OFFICE'
            WHEN TYPE = 'Address for Service' THEN 'SERVICE'
            ELSE 'PUBLIC'
        END AS address_type,
        CASE WHEN START_DATE != '' THEN strptime(START_DATE, '%d/%m/%Y')::DATE END AS start_date,
        CASE WHEN trim(coalesce(ADDRESS_CARE_OF, '')) != '' THEN trim(ADDRESS_CARE_OF) END AS care_of,
        CASE WHEN trim(coalesce(ADDRESS_PAF_ID, '')) != '' THEN trim(ADDRESS_PAF_ID) END AS paf_id,
        coalesce(ADDRESS_1, '') AS street,
        CASE WHEN trim(coalesce(ADDRESS_2, '')) != '' THEN trim(ADDRESS_2) END AS suburb,
        coalesce(
            CASE WHEN trim(coalesce(ADDRESS_3, '')) != '' THEN trim(ADDRESS_3) END,
            CASE WHEN trim(coalesce(ADDRESS_4, '')) != '' THEN trim(ADDRESS_4) END,
            ''
        ) AS city,
        CASE WHEN trim(coalesce(ADDRESS_POSTCODE, '')) != '' THEN trim(ADDRESS_POSTCODE) END AS postcode,
        coalesce(ADDRESS_COUNTRY, '') AS country
    FROM read_parquet($input_public, hive_partitioning = false)
),
unioned AS (
    SELECT * FROM reg_office
    UNION ALL
    SELECT * FROM service
    UNION ALL
    SELECT * FROM public_addr
)
SELECT
    nzbn,
    address_type,
    start_date,
    care_of,
    paf_id,
    street,
    suburb,
    city,
    postcode,
    country,
    $month AS snapshot_month
FROM unioned
WHERE street != '' OR city != '' OR country != ''
QUALIFY row_number() OVER (PARTITION BY nzbn, address_type ORDER BY start_date DESC) = 1
