SELECT
    nzbn AS NZBN,
    company_number AS COMPANY_IDENTIFIER,
    entity_name AS ENTITY_NAME,
    incorporation_date AS INCORPORATION_DATE,
    removal_date AS REMOVAL_DATE,
    entity_type AS ENTITY_TYPE,
    entity_status AS ENTITY_STATUS,
    coalesce(abn, '') AS ABN,
    coalesce(gst_number, '') AS GST_NUMBER,
    coalesce(website, '') AS WEBSITE,
    coalesce(maori_business_identifier, '') AS MAORI_BUSINESS_IDENTIFIER
FROM read_parquet($input_path, hive_partitioning = false)
