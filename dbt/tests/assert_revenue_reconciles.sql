-- Revenue in the order fact must equal the sum of its items (no rows lost or double counted in joins).
select 1
from (select sum(revenue) as r from {{ ref('fct_orders') }}) o,
     (select sum(revenue) as r from {{ ref('fct_order_items') }}) i
where abs(o.r - i.r) > 0.01
