{% macro normalize_text(column) -%}
lower(
    trim(
        regexp_replace(
            translate({{ column }}::text, 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun'),
            '[[:space:]]+', ' ', 'g'
        )
    )
)
{%- endmacro %}

{% macro normalize_lexical(column) -%}
trim(
    regexp_replace(
        {{ normalize_text(column) }},
        '[^a-z0-9]+', ' ', 'g'
    )
)
{%- endmacro %}
