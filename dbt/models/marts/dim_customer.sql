-- Olist issues a new customer_id per order; customer_unique_id is the real person.
-- Keep customer_id as the key (it is what orders reference) and expose the person id.
select
    c.customer_id,
    c.customer_unique_id,
    c.city,
    c.state,
    c.zip_prefix,
    g.lat,
    g.lng
from {{ ref('stg_customers') }} c
left join {{ ref('stg_geolocation') }} g using (zip_prefix)
