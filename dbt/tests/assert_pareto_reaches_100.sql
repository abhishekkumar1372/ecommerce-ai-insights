-- The cumulative Pareto share must end at exactly 100% of revenue.
select max(cumulative_share) from {{ ref('kpi_category_pareto') }}
having abs(max(cumulative_share) - 1) > 0.0001
