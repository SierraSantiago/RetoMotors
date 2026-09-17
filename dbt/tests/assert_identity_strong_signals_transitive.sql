with leads as (
    select raw_row_id, empresa_id, lead_id, telefono_normalizado,
           telefono_parse_status, email_normalizado
    from {{ ref('stg_leads') }}
), mapped as (
    select raw_row_id, customer_identity_id
    from {{ ref('int_lead_identity_map') }}
), valid_emails as (
    select * from leads
    where email_normalizado is not null
      and email_normalizado ~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$'
), signal_pairs as (
    select a.raw_row_id as a_row, b.raw_row_id as b_row
    from leads a join leads b
      on a.raw_row_id < b.raw_row_id
     and a.empresa_id = b.empresa_id
     and a.telefono_parse_status = 'VALID'
     and a.telefono_normalizado = b.telefono_normalizado
    union
    select a.raw_row_id, b.raw_row_id
    from valid_emails a join valid_emails b
      on a.raw_row_id < b.raw_row_id
     and a.empresa_id = b.empresa_id
     and a.email_normalizado = b.email_normalizado
    union
    select a.raw_row_id, b.raw_row_id
    from leads a join leads b
      on a.raw_row_id < b.raw_row_id
     and a.empresa_id = b.empresa_id
     and nullif(trim(a.lead_id), '') is not null
     and a.lead_id = b.lead_id
), violations as (
    select a.a_row, a.b_row
    from signal_pairs a
    join mapped ma on ma.raw_row_id = a.a_row
    join mapped mb on mb.raw_row_id = a.b_row
    where ma.customer_identity_id <> mb.customer_identity_id
)
select * from violations
