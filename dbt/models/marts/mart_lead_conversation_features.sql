{{ config(materialized='table') }}

with linked as (
    select c.*
    from {{ ref('int_conversation_extractions_current') }} c
    where c.lead_id is not null
      and exists (
          select 1
          from {{ ref('stg_leads') }} l
          where l.lead_id = c.lead_id
      )
), ordered as (
    select
        linked.*,
        row_number() over (
            partition by lead_id
            order by conversation_started_at desc nulls last, conversation_id desc
        ) as latest_rank
    from linked
), latest_non_null as (
    select
        lead_id,
        (array_agg(modelo_interes order by conversation_started_at desc nulls last, conversation_id desc)
            filter (where modelo_interes is not null))[1] as modelo_interes,
        (array_agg(presupuesto order by conversation_started_at desc nulls last, conversation_id desc)
            filter (where presupuesto is not null))[1] as presupuesto,
        (array_agg(cuota_inicial order by conversation_started_at desc nulls last, conversation_id desc)
            filter (where cuota_inicial is not null))[1] as cuota_inicial,
        (array_agg(objecion_principal order by conversation_started_at desc nulls last, conversation_id desc)
            filter (where objecion_principal is not null))[1] as objecion_principal,
        (array_agg(intencion order by conversation_started_at desc nulls last, conversation_id desc)
            filter (where intencion is not null and intencion <> 'indeterminada'))[1] as intencion
    from linked
    group by lead_id
), latest_payment as (
    select distinct on (lead_id)
        lead_id,
        forma_pago
    from linked
    where forma_pago in ('credito', 'contado')
    order by lead_id, conversation_started_at desc nulls last, conversation_id desc
), rollup as (
    select
        lead_id,
        count(*) as conversation_count,
        array_agg(conversation_id order by conversation_started_at asc nulls last, conversation_id asc)
            as conversation_ids,
        min(conversation_started_at) as first_conversation_at,
        max(conversation_started_at) as latest_conversation_at,
        max(conversation_id) filter (where latest_rank = 1) as latest_conversation_id,
        bool_or(coalesce(pidio_cita, false)) as pidio_cita,
        bool_or(coalesce(pidio_cotizacion, false)) as pidio_cotizacion,
        bool_and(coalesce(evidence_grounded, false)) as conversation_evidence_grounded_all,
        count(*) filter (where evidence_grounded is true)
            as conversation_evidence_grounded_count,
        count(*) filter (where evidence_grounded is false)
            as conversation_evidence_not_grounded_count
    from ordered
    group by lead_id
)
select
    r.lead_id,
    r.conversation_count,
    r.conversation_ids,
    r.first_conversation_at,
    r.latest_conversation_at,
    r.latest_conversation_id,
    n.modelo_interes,
    n.presupuesto,
    n.cuota_inicial,
    coalesce(p.forma_pago, 'no_informa') as forma_pago,
    coalesce(n.intencion, 'indeterminada') as intencion,
    n.objecion_principal,
    r.pidio_cita,
    r.pidio_cotizacion,
    r.conversation_evidence_grounded_all,
    r.conversation_evidence_grounded_count,
    r.conversation_evidence_not_grounded_count
from rollup r
left join latest_non_null n using (lead_id)
left join latest_payment p using (lead_id)
