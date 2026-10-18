with bounds as (
    select min(purchased_at)::date as lo, (max(purchased_at) + interval '90 days')::date as hi
    from {{ ref('stg_orders') }}
)
select
    d::date                                   as date_day,
    to_char(d, 'YYYYMMDD')::int               as date_key,
    extract(year from d)::int                 as year,
    extract(quarter from d)::int              as quarter,
    extract(month from d)::int                as month,
    to_char(d, 'Mon')                         as month_name,
    date_trunc('month', d)::date              as month_start,
    date_trunc('week', d)::date               as week_start,
    extract(isodow from d)::int               as day_of_week,
    to_char(d, 'Dy')                          as day_name,
    extract(isodow from d) in (6, 7)          as is_weekend
from bounds, generate_series(lo, hi, interval '1 day') as d
