{% macro date_input(column) -%}
trim({{ column }}::text)
{%- endmacro %}

{% macro date_valid(year, month, day) -%}
({{ year }} between 1 and 9999 and {{ month }} between 1 and 12 and {{ day }} between 1 and extract(day from (make_date({{ year }}, {{ month }}, 1) + interval '1 month - 1 day')))
{%- endmacro %}

{% macro safe_date_status(column) -%}
case
    when {{ column }} is null or {{ date_input(column) }} = '' then 'MISSING'
    when {{ date_input(column) }} ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}([ T].*)?$'
        then case when {{ date_valid("substring(" ~ date_input(column) ~ " from 1 for 4)::int", "substring(" ~ date_input(column) ~ " from 6 for 2)::int", "substring(" ~ date_input(column) ~ " from 9 for 2)::int") }} then 'VALID' else 'INVALID' end
    when {{ date_input(column) }} ~ '^[0-9]{2}-[0-9]{2}-[0-9]{4}$'
        then case when {{ date_valid("substring(" ~ date_input(column) ~ " from 7 for 4)::int", "substring(" ~ date_input(column) ~ " from 4 for 2)::int", "substring(" ~ date_input(column) ~ " from 1 for 2)::int") }} then 'VALID' else 'INVALID' end
    when {{ date_input(column) }} ~ '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}([ T].*)?$'
        then case
            when split_part(left({{ date_input(column) }}, 10), '/', 1)::int <= 12 and split_part(left({{ date_input(column) }}, 10), '/', 2)::int <= 12 then 'AMBIGUOUS'
            when split_part(left({{ date_input(column) }}, 10), '/', 1)::int > 12
                then case when {{ date_valid("split_part(left(" ~ date_input(column) ~ ", 10), '/', 3)::int", "split_part(left(" ~ date_input(column) ~ ", 10), '/', 2)::int", "split_part(left(" ~ date_input(column) ~ ", 10), '/', 1)::int") }} then 'VALID' else 'INVALID' end
            else case when {{ date_valid("split_part(left(" ~ date_input(column) ~ ", 10), '/', 3)::int", "split_part(left(" ~ date_input(column) ~ ", 10), '/', 1)::int", "split_part(left(" ~ date_input(column) ~ ", 10), '/', 2)::int") }} then 'VALID' else 'INVALID' end
        end
    else 'INVALID'
end
{%- endmacro %}

{% macro safe_date_value(column) -%}
case
    when {{ safe_date_status(column) }} <> 'VALID' then null::date
    when {{ date_input(column) }} ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}' then make_date(substring({{ date_input(column) }} from 1 for 4)::int, substring({{ date_input(column) }} from 6 for 2)::int, substring({{ date_input(column) }} from 9 for 2)::int)
    when {{ date_input(column) }} ~ '^[0-9]{2}-[0-9]{2}-[0-9]{4}$' then make_date(substring({{ date_input(column) }} from 7 for 4)::int, substring({{ date_input(column) }} from 4 for 2)::int, substring({{ date_input(column) }} from 1 for 2)::int)
    when split_part(left({{ date_input(column) }}, 10), '/', 1)::int > 12 then make_date(split_part(left({{ date_input(column) }}, 10), '/', 3)::int, split_part(left({{ date_input(column) }}, 10), '/', 2)::int, split_part(left({{ date_input(column) }}, 10), '/', 1)::int)
    else make_date(split_part(left({{ date_input(column) }}, 10), '/', 3)::int, split_part(left({{ date_input(column) }}, 10), '/', 1)::int, split_part(left({{ date_input(column) }}, 10), '/', 2)::int)
end
{%- endmacro %}
