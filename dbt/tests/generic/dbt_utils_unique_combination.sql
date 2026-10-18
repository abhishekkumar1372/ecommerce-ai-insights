{# Small local version of dbt_utils.unique_combination_of_columns, so the project has no package dependency. #}
{% test dbt_utils_unique_combination(model, columns) %}
select {{ columns | join(', ') }}, count(*)
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}
