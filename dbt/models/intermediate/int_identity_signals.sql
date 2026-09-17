with leads as (
    select
        raw_row_id,
        lead_id,
        empresa_id,
        telefono_normalizado,
        telefono_parse_status,
        email_normalizado
    from {{ ref('stg_leads') }}
), valid_emails as (
    select *
    from leads
    where email_normalizado is not null
      and email_normalizado ~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$'
      and lower(email_normalizado) not in (
          'test@test.com', 'test@example.com', 'test@example.org',
          'example@example.com', 'noemail@noemail.com', 'no@no.com',
          'none@none.com', 'null@null.com', 'n/a@n/a.com'
      )
      and lower(email_normalizado) not like 'test@%'
      and lower(email_normalizado) not like 'prueba@%'
      and lower(email_normalizado) not like 'noemail@%'
), signals as (
    select raw_row_id, lead_id, empresa_id, 'SOURCE_LEAD_ID' as signal_type,
           trim(lead_id) as signal_value
    from leads
    where nullif(trim(lead_id), '') is not null
      and empresa_id is not null
    union all
    select raw_row_id, lead_id, empresa_id, 'PHONE', telefono_normalizado
    from leads
    where telefono_parse_status = 'VALID'
      and nullif(trim(telefono_normalizado), '') is not null
      and empresa_id is not null
    union all
    select raw_row_id, lead_id, empresa_id, 'EMAIL', email_normalizado
    from valid_emails
)
select distinct raw_row_id, lead_id, empresa_id, signal_type, signal_value
from signals
