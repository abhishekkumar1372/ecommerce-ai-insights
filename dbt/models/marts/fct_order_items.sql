-- Grain: one row per item sold. The main fact table for revenue, product and seller analysis.
-- Freight outliers (above the 99.9th percentile) are flagged rather than dropped.
with freight_cap as (
    select percentile_cont(0.999) within group (order by freight_value) as p999
    from {{ ref('stg_order_items') }}
)
select
    i.order_id,
    i.order_item_id,
    o.customer_id,
    i.product_id,
    i.seller_id,
    to_char(o.purchased_at, 'YYYYMMDD')::int            as date_key,
    o.purchased_at,
    o.order_status,
    i.price                                             as revenue,
    i.freight_value,
    round(i.price * p.assumed_margin_pct, 2)            as est_gross_profit,
    i.freight_value > f.p999                            as is_freight_outlier
from {{ ref('stg_order_items') }} i
join {{ ref('stg_orders') }} o using (order_id)
join {{ ref('dim_product') }} p using (product_id)
cross join freight_cap f
