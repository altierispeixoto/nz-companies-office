SELECT
    md5(street || '|' || city || '|' || country) AS address_key,
    street,
    city,
    country,
    max(suburb) AS suburb,
    max(postcode) AS postcode,
    max(care_of) AS care_of,
    max(paf_id) AS paf_id
FROM read_parquet($silver_glob, hive_partitioning = false)
GROUP BY street, city, country
