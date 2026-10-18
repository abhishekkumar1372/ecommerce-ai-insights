-- Monthly KPI revenue must add up to fact revenue for the same orders.
select 1
from (select sum(revenue) r from {{ ref('kpi_monthly_sales') }}) k,
     (select sum(revenue) r from {{ ref('fct_orders') }} where order_status not in ('canceled', 'unavailable')) f
where abs(k.r - f.r) > 1
