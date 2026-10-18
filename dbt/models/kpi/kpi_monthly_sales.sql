-- Monthly headline KPIs with growth and trend metrics.
-- Window functions: LAG for MoM / YoY, AVG OVER for a 3-month moving average,
-- SUM OVER for a running total.
with monthly as (
    select
        date_trunc('month', purchased_at)::date        as month,
        count(*)                                       as orders,
        count(distinct customer_unique_id)             as customers,
        sum(revenue)                                   as revenue,
        sum(est_gross_profit)                          as est_gross_profit,
        sum(freight)                                   as freight,
        avg(review_score)                              as avg_review_score,
        avg(is_late::int)                              as late_delivery_rate
    from {{ ref('fct_orders') }}
    where order_status not in ('canceled', 'unavailable')
    group by 1
)
select
    month,
    orders,
    customers,
    round(revenue, 2)                                                       as revenue,
    round(est_gross_profit, 2)                                              as est_gross_profit,
    round(est_gross_profit / nullif(revenue, 0), 4)                         as est_margin_pct,
    round(revenue / nullif(orders, 0), 2)                                   as avg_order_value,
    round(avg_review_score, 2)                                              as avg_review_score,
    round(late_delivery_rate, 4)                                            as late_delivery_rate,
    round(revenue / nullif(lag(revenue) over w, 0) - 1, 4)                  as revenue_mom_growth,
    round(revenue / nullif(lag(revenue, 12) over w, 0) - 1, 4)              as revenue_yoy_growth,
    round(avg(revenue) over (w rows between 2 preceding and current row), 2) as revenue_3m_moving_avg,
    round(sum(revenue) over (w rows unbounded preceding), 2)                as revenue_running_total
from monthly
window w as (order by month)
order by month
