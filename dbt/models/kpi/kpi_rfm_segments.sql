-- RFM segmentation per real customer (customer_unique_id).
-- Recency, Frequency and Monetary are each scored 1-5 with NTILE, then mapped to segments.
with snapshot as (
    select max(purchased_at)::date + 1 as as_of from {{ ref('fct_orders') }}
),
customer as (
    select
        o.customer_unique_id,
        max(o.purchased_at)::date                        as last_order_date,
        count(*)                                         as frequency,
        sum(o.revenue)                                   as monetary,
        min(c.state)                                     as state
    from {{ ref('fct_orders') }} o
    join {{ ref('dim_customer') }} c using (customer_id)
    where o.order_status not in ('canceled', 'unavailable')
    group by 1
),
scored as (
    select
        c.*,
        s.as_of - c.last_order_date                                   as recency_days,
        ntile(5) over (order by s.as_of - c.last_order_date desc)     as r_score,
        -- Most customers order once, so frequency ties are broken by spend.
        ntile(5) over (order by c.frequency, c.monetary)              as f_score,
        ntile(5) over (order by c.monetary)                           as m_score
    from customer c cross join snapshot s
)
select
    customer_unique_id,
    state,
    last_order_date,
    recency_days,
    frequency,
    round(monetary, 2)                                        as monetary,
    r_score, f_score, m_score,
    r_score::text || f_score::text || m_score::text           as rfm_code,
    case
        when r_score >= 4 and f_score >= 4 and m_score >= 4 then 'Champions'
        when r_score >= 3 and f_score >= 3                  then 'Loyal'
        when r_score >= 4 and f_score <= 2                  then 'New / Promising'
        when r_score <= 2 and m_score >= 4                  then 'At Risk (high value)'
        when r_score <= 2 and f_score <= 2                  then 'Lost'
        else 'Needs Attention'
    end                                                       as segment
from scored
