select
    order_id,
    payment_sequential::int                    as payment_sequential,
    lower(trim(payment_type))                  as payment_type,
    greatest(payment_installments::int, 1)     as installments,
    payment_value::numeric(12, 2)              as payment_value
from {{ source('raw', 'order_payments') }}
where payment_type <> 'not_defined'
