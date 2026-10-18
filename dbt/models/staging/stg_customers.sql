select
    customer_id,
    customer_unique_id,
    lpad(customer_zip_code_prefix, 5, '0')     as zip_prefix,
    {{ clean_city('customer_city') }}          as city,
    upper(trim(customer_state))                as state
from {{ source('raw', 'customers') }}
