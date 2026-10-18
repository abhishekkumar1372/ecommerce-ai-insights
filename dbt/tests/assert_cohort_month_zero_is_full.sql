-- By definition every cohort is 100% active in its first month.
select * from {{ ref('kpi_cohort_retention') }}
where months_since_first = 0 and retention_rate <> 1
