-- Translate categories to English. Categories missing from the translation file
-- fall back to the Portuguese name; products with no category become 'unknown'.
select
    p.product_id,
    coalesce(t.product_category_name_english, p.product_category_name, 'unknown') as category,
    p.product_category_name                                                       as category_pt,
    nullif(p.product_photos_qty, '')::int                                         as photos_qty,
    nullif(p.product_weight_g, '')::int                                           as weight_g,
    nullif(p.product_length_cm, '')::int * nullif(p.product_height_cm, '')::int
        * nullif(p.product_width_cm, '')::int                                     as volume_cm3
from {{ source('raw', 'products') }} p
left join {{ source('raw', 'product_category_name_translation') }} t
    on t.product_category_name = p.product_category_name
