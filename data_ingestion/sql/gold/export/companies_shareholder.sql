WITH representative AS (
    SELECT
        nzbn,
        shareholder_name,
        start_date,
        sh_status,
        parcel_id,
        assignment_id,
        address_care_of,
        address_street,
        address_suburb,
        address_city,
        address_postcode,
        address_country
    FROM read_parquet($silver_glob, hive_partitioning = false)
    QUALIFY row_number() OVER (
        PARTITION BY nzbn, shareholder_name
        ORDER BY snapshot_month DESC, start_date DESC
    ) = 1
)
SELECT
    sh.nzbn AS NZBN,
    sh.shareholder_name AS SHAREHOLDER_NAME,
    coalesce(sh.sh_type, '') AS SH_TYPE,
    CASE WHEN sh.is_person THEN 'true' ELSE 'false' END AS IS_PERSON,
    sh.name_key AS NAME_KEY,
    sh.shares AS NUMBER_OF_SHARES,
    CASE WHEN sh.extensive_shareholding THEN 'true' ELSE 'false' END AS EXTENSIVE_SHAREHOLDING,
    coalesce(r.sh_status, '') AS SH_STATUS,
    coalesce(strftime(r.start_date, '%Y-%m-%d'), '') AS START_DATE,
    coalesce(r.parcel_id, '') AS PARCEL_ID,
    coalesce(r.assignment_id, '') AS ASSIGNMENT_ID,
    sh.share_percentage AS SHARE_PERCENTAGE,
    CASE WHEN sh.is_majority THEN 'true' ELSE 'false' END AS IS_MAJORITY,
    coalesce(r.address_care_of, '') AS ADDRESS_CARE_OF,
    coalesce(r.address_street, '') AS ADDRESS_STREET,
    coalesce(r.address_suburb, '') AS ADDRESS_SUBURB,
    coalesce(r.address_city, '') AS ADDRESS_CITY,
    coalesce(r.address_postcode, '') AS ADDRESS_POSTCODE,
    coalesce(r.address_country, '') AS ADDRESS_COUNTRY
FROM read_parquet($gold_path, hive_partitioning = false) AS sh
JOIN representative AS r ON sh.nzbn = r.nzbn AND sh.shareholder_name = r.shareholder_name
