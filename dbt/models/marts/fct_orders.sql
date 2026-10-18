-- Grain: one row per order, with delivery performance and review outcome.
with items as (
    select order_id, count(*) as item_count, sum(revenue) as revenue,
           sum(freight_value) as freight, sum(est_gross_profit) as est_gross_profit
    from {{ ref('fct_order_items') }}
    group by 1
),
payments as (
    select order_id, sum(payment_value) as amount_paid, max(installments) as max_installments,
           (array_agg(payment_type order by payment_value desc))[1] as main_payment_type
    from {{ ref('stg_payments') }}
    group by 1
)
select
    o.order_id,
    o.customer_id,
    c.customer_unique_id,
    to_char(o.purchased_at, 'YYYYMMDD')::int                         as date_key,
    o.purchased_at,
    o.order_status,
    coalesce(i.item_count, 0)                                        as item_count,
    coalesce(i.revenue, 0)                                           as revenue,
    coalesce(i.freight, 0)                                           as freight,
    coalesce(i.est_gross_profit, 0)                                  as est_gross_profit,
    p.amount_paid,
    p.main_payment_type,
    p.max_installments,
    o.estimated_delivery_date,
    o.delivered_at,
    extract(epoch from o.delivered_at - o.purchased_at) / 86400.0    as delivery_days,
    case when o.delivered_at is null then null
         else o.delivered_at::date > o.estimated_delivery_date end   as is_late,
    r.review_score,
    r.comment_message                                                as review_comment
from {{ ref('stg_orders') }} o
join {{ ref('dim_customer') }} c using (customer_id)
left join items i using (order_id)
left join payments p using (order_id)
left join {{ ref('stg_reviews') }} r using (order_id)
