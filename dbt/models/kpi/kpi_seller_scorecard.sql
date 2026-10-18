-- Seller scorecard: sales, delivery and review performance, with a percentile
-- rank on revenue and a simple flag for sellers needing attention.
with seller as (
    select
        f.seller_id,
        count(distinct f.order_id)            as orders,
        sum(f.revenue)                        as revenue,
        avg(o.review_score)                   as avg_review_score,
        avg(o.is_late::int)                   as late_rate
    from {{ ref('fct_order_items') }} f
    join {{ ref('fct_orders') }} o using (order_id)
    where f.order_status = 'delivered'
    group by 1
)
select
    s.seller_id,
    d.state,
    s.orders,
    round(s.revenue, 2)                                           as revenue,
    round(s.avg_review_score, 2)                                  as avg_review_score,
    round(s.late_rate, 4)                                         as late_rate,
    round(percent_rank() over (order by s.revenue)::numeric, 4)   as revenue_percentile,
    s.orders >= 10 and (s.avg_review_score < 3.5 or s.late_rate > 0.2) as needs_attention
from seller s
join {{ ref('dim_seller') }} d using (seller_id)
