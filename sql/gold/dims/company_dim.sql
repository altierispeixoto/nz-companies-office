WITH company AS (
    SELECT
        nzbn,
        company_number,
        entity_name,
        entity_type,
        entity_status,
        incorporation_date,
        removal_date,
        snapshot_month AS as_of_snapshot_month
    FROM read_parquet($silver_glob, hive_partitioning = false)
    QUALIFY row_number() OVER (PARTITION BY nzbn ORDER BY snapshot_month DESC) = 1
),
abn AS (
    SELECT nzbn, abn
    FROM read_parquet($abn_glob, hive_partitioning = false)
    QUALIFY row_number() OVER (PARTITION BY nzbn ORDER BY snapshot_month DESC) = 1
),
gst AS (
    SELECT nzbn, gst_number
    FROM read_parquet($gst_glob, hive_partitioning = false)
    QUALIFY row_number() OVER (PARTITION BY nzbn ORDER BY snapshot_month DESC) = 1
),
website AS (
    SELECT nzbn, website
    FROM read_parquet($website_glob, hive_partitioning = false)
    QUALIFY row_number() OVER (PARTITION BY nzbn ORDER BY snapshot_month DESC) = 1
),
maori AS (
    SELECT nzbn, maori_business_identifier
    FROM read_parquet($maori_glob, hive_partitioning = false)
    QUALIFY row_number() OVER (PARTITION BY nzbn ORDER BY snapshot_month DESC) = 1
)
SELECT
    company.nzbn,
    company.company_number,
    company.entity_name,
    company.entity_type,
    company.entity_status,
    company.incorporation_date,
    company.removal_date,
    abn.abn,
    gst.gst_number,
    website.website,
    maori.maori_business_identifier,
    company.as_of_snapshot_month
FROM company
LEFT JOIN abn ON company.nzbn = abn.nzbn
LEFT JOIN gst ON company.nzbn = gst.nzbn
LEFT JOIN website ON company.nzbn = website.nzbn
LEFT JOIN maori ON company.nzbn = maori.nzbn
