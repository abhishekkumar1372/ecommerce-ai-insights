-- Top 5 products in each category by revenue (DENSE_RANK per partition).
with product_sales as (
    select
        p.category,
        f.product_id,
        count(*)            as units_sold,
        sum(f.revenue)      as revenue,
        avg(o.review_score) as avg_review_score
    from {{ ref('fct_order_items') }} f
    join {{ ref('dim_product') }} p using (product_id)
    join {{ ref('fct_orders') }} o using (order_id)
    where f.order_status not in ('canceled', 'unavailable')
    group by 1, 2
),
ranked as (
    select *, dense_rank() over (partition by category order by revenue desc) as rank_in_category
    from product_sales
)
select category, product_id, rank_in_category, units_sold,
       round(revenue, 2) as revenue, round(avg_review_score, 2) as avg_review_score
from ranked
where rank_in_category <= 5
