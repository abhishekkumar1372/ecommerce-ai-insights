-- The source has exact duplicate rows and some orders with several reviews.
-- Keep one row per review_id, then the latest answered review per order.
with deduped as (
    select distinct on (review_id, order_id)
        review_id,
        order_id,
        review_score::int                                      as review_score,
        nullif(trim(review_comment_title), '')                 as comment_title,
        nullif(trim(review_comment_message), '')               as comment_message,
        review_creation_date::timestamp                        as created_at,
        review_answer_timestamp::timestamp                     as answered_at
    from {{ source('raw', 'order_reviews') }}
    order by review_id, order_id, review_answer_timestamp desc
),
ranked as (
    select *, row_number() over (partition by order_id order by answered_at desc) as rn
    from deduped
)
select review_id, order_id, review_score, comment_title, comment_message, created_at, answered_at
from ranked
where rn = 1
