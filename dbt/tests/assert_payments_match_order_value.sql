-- For delivered orders, payments should cover items + freight (within 1%, allowing for
-- vouchers and rounding). Warn rather than fail: the real data has a few exceptions.
{{ config(severity='warn') }}
select order_id, revenue + freight as order_value, amount_paid
from {{ ref('fct_orders') }}
where order_status = 'delivered'
  and amount_paid is not null
  and abs(amount_paid - (revenue + freight)) > 0.01 * (revenue + freight) + 1
