{% macro grant_ai_readonly(schemas) %}
  {% set role_exists = run_query("select 1 from pg_roles where rolname = 'ai_readonly'") %}
  {% if execute and role_exists.rows | length > 0 %}
    {% for s in schemas %}
      grant usage on schema {{ s }} to ai_readonly;
      grant select on all tables in schema {{ s }} to ai_readonly;
    {% endfor %}
  {% else %}
    select 1
  {% endif %}
{% endmacro %}
