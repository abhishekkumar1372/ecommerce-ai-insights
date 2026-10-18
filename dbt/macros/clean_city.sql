{# Lowercase, trim and strip Portuguese accents so "São Paulo", "SAO PAULO" and "sao paulo" match. #}
{% macro clean_city(col) -%}
    lower(trim(translate({{ col }}, 'áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ',
                                    'aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUC')))
{%- endmacro %}
