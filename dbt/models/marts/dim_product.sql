select
    p.product_id,
    p.category,
    p.category_pt,
    p.photos_qty,
    p.weight_g,
    p.volume_cm3,
    coalesce(m.gross_margin_pct, d.gross_margin_pct)::numeric(4, 3) as assumed_margin_pct
from {{ ref('stg_products') }} p
left join {{ ref('category_margins') }} m on m.category = p.category
cross join (select gross_margin_pct from {{ ref('category_margins') }} where category = '_default') d
