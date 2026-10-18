-- The source has many points per zip prefix; keep one centroid per prefix.
select
    lpad(geolocation_zip_code_prefix, 5, '0')  as zip_prefix,
    avg(geolocation_lat::numeric)::numeric(9, 6) as lat,
    avg(geolocation_lng::numeric)::numeric(9, 6) as lng,
    upper(min(geolocation_state))              as state
from {{ source('raw', 'geolocation') }}
group by 1
