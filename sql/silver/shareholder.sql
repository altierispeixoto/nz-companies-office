SELECT
    NZBN AS nzbn,
    ENTITY_NAME AS company_name,
    SH_NAME AS shareholder_name,
    CASE WHEN trim(coalesce(SH_TYPE, '')) != '' THEN trim(SH_TYPE) END AS sh_type,
    CASE WHEN START_DATE != '' THEN strptime(START_DATE, '%d/%m/%Y')::DATE END AS start_date,
    CASE WHEN trim(coalesce(SH_STATUS, '')) != '' THEN trim(SH_STATUS) END AS sh_status,
    CASE WHEN coalesce(PARCEL_IDENTIFIER, '') != '' THEN PARCEL_IDENTIFIER END AS parcel_id,
    CASE WHEN coalesce(ASSIGNMENT_IDENTIFIER, '') != '' THEN ASSIGNMENT_IDENTIFIER END AS assignment_id,
    CASE WHEN NUMBER_OF_SHARES != '' THEN CAST(NUMBER_OF_SHARES AS BIGINT) ELSE 0 END AS number_of_shares,
    (trim(coalesce(SH_EXTENSIVE_SHAREHOLDING_YN, '')) = 'Y') AS extensive_shareholding,
    CASE WHEN trim(coalesce(SH_ADDRESS_CARE_OF, '')) != '' THEN trim(SH_ADDRESS_CARE_OF) END AS address_care_of,
    CASE WHEN trim(coalesce(SH_ADDRESS_PAF_ID, '')) != '' THEN trim(SH_ADDRESS_PAF_ID) END AS address_paf_id,
    coalesce(SH_ADDRESS_1, '') AS address_street,
    CASE WHEN trim(coalesce(SH_ADDRESS_2, '')) != '' THEN trim(SH_ADDRESS_2) END AS address_suburb,
    coalesce(
        CASE WHEN trim(coalesce(SH_ADDRESS_3, '')) != '' THEN trim(SH_ADDRESS_3) END,
        CASE WHEN trim(coalesce(SH_ADDRESS_4, '')) != '' THEN trim(SH_ADDRESS_4) END,
        ''
    ) AS address_city,
    CASE WHEN trim(coalesce(SH_ADDRESS_POSTCODE, '')) != '' THEN trim(SH_ADDRESS_POSTCODE) END AS address_postcode,
    coalesce(SH_ADDRESS_COUNTRY, '') AS address_country,
    trim(regexp_replace(SH_NAME, '\s+', ' ', 'g')) AS normalized_name,
    regexp_matches(trim(regexp_replace(SH_NAME, '\s+', ' ', 'g')), '[a-z]') AS is_person,
    upper(list_extract(string_split(trim(regexp_replace(SH_NAME, '\s+', ' ', 'g')), ' '), 1))
        || upper(list_extract(string_split(trim(regexp_replace(SH_NAME, '\s+', ' ', 'g')), ' '), -1)) AS name_key,
    $month AS snapshot_month
FROM read_parquet($input_path, hive_partitioning = false)
QUALIFY row_number() OVER (
    PARTITION BY NZBN, SH_NAME, PARCEL_IDENTIFIER, ASSIGNMENT_IDENTIFIER
    ORDER BY START_DATE
) = 1
