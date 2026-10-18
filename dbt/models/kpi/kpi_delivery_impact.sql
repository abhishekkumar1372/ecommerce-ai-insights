-- How delivery performance drives customer satisfaction, by customer state.
select
    c.state,
    count(*)                                                            as delivered_orders,
    round(avg(o.delivery_days)::numeric, 1)                             as avg_delivery_days,
    round(avg(o.is_late::int), 4)                                       as late_rate,
    round(avg(o.review_score) filter (where not o.is_late), 2)          as review_on_time,
    round(avg(o.review_score) filter (where o.is_late), 2)              as review_late,
    round(avg(o.review_score) filter (where not o.is_late)
          - avg(o.review_score) filter (where o.is_late), 2)            as review_drop_when_late,
    round(sum(o.revenue), 2)                                            as revenue
from {{ ref('fct_orders') }} o
join {{ ref('dim_customer') }} c using (customer_id)
where o.order_status = 'delivered' and o.delivered_at is not null
group by 1
