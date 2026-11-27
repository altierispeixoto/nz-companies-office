SELECT
    ca.nzbn AS NZBN,
    ca.address_type AS ADDRESS_TYPE,
    coalesce(strftime(ca.since, '%Y-%m-%d'), '') AS START_DATE,
    ad.street AS STREET,
    coalesce(ad.suburb, '') AS SUBURB,
    ad.city AS CITY,
    coalesce(ad.postcode, '') AS POSTCODE,
    ad.country AS COUNTRY
FROM read_parquet($company_address_path, hive_partitioning = false) AS ca
JOIN read_parquet($address_dim_path, hive_partitioning = false) AS ad ON ca.address_key = ad.address_key
