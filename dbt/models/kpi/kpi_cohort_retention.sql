-- Monthly cohort retention: customers grouped by first-purchase month, and the
-- share still buying N months later. Feeds the cohort heatmap.
with orders as (
    select customer_unique_id, date_trunc('month', purchased_at)::date as order_month
    from {{ ref('fct_orders') }}
    where order_status not in ('canceled', 'unavailable')
),
first_purchase as (
    select customer_unique_id, min(order_month) as cohort_month
    from orders group by 1
),
activity as (
    select distinct
        f.cohort_month,
        o.customer_unique_id,
        (extract(year from age(o.order_month, f.cohort_month)) * 12
         + extract(month from age(o.order_month, f.cohort_month)))::int as months_since_first
    from orders o join first_purchase f using (customer_unique_id)
),
counts as (
    select cohort_month, months_since_first, count(*) as active_customers
    from activity group by 1, 2
)
select
    cohort_month,
    months_since_first,
    active_customers,
    first_value(active_customers) over (partition by cohort_month order by months_since_first) as cohort_size,
    round(active_customers::numeric
          / first_value(active_customers) over (partition by cohort_month order by months_since_first), 4)
        as retention_rate
from counts
