select
    order_id,
    customer_id,
    lower(trim(order_status))                                as order_status,
    order_purchase_timestamp::timestamp                      as purchased_at,
    nullif(order_approved_at, '')::timestamp                 as approved_at,
    nullif(order_delivered_carrier_date, '')::timestamp      as shipped_at,
    nullif(order_delivered_customer_date, '')::timestamp     as delivered_at,
    order_estimated_delivery_date::timestamp::date           as estimated_delivery_date
from {{ source('raw', 'orders') }}
