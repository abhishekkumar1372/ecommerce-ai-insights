-- Category performance and the Pareto (80/20) curve: what share of revenue
-- the top categories bring, using a running SUM OVER ordered by revenue.
with by_category as (
    select
        p.category,
        count(distinct f.order_id)        as orders,
        sum(f.revenue)                    as revenue,
        sum(f.est_gross_profit)           as est_gross_profit
    from {{ ref('fct_order_items') }} f
    join {{ ref('dim_product') }} p using (product_id)
    where f.order_status not in ('canceled', 'unavailable')
    group by 1
)
select
    category,
    orders,
    round(revenue, 2)                                                           as revenue,
    round(est_gross_profit, 2)                                                  as est_gross_profit,
    rank() over (order by revenue desc)                                         as revenue_rank,
    round(revenue / sum(revenue) over (), 4)                                    as revenue_share,
    round(sum(revenue) over (order by revenue desc rows unbounded preceding)
          / sum(revenue) over (), 4)                                            as cumulative_share,
    sum(revenue) over (order by revenue desc rows unbounded preceding)
        - revenue < 0.8 * sum(revenue) over ()                                  as is_top_80_pct
from by_category
