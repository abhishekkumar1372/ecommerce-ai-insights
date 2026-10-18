select
    seller_id,
    lpad(seller_zip_code_prefix, 5, '0')       as zip_prefix,
    {{ clean_city('seller_city') }}            as city,
    upper(trim(seller_state))                  as state
from {{ source('raw', 'sellers') }}
