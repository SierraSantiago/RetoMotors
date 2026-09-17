{{ config(materialized='view') }}

with ranked_success as (
    select
        e.*,
        row_number() over (
            partition by e.conversation_id
            order by e.processed_at desc nulls last,
                     e.updated_at desc nulls last,
                     e.extraction_id
        ) as extraction_rank
    from ai.conversation_extractions e
    where e.status = 'SUCCESS'
), conversations as (
    select
        conversacion_id as conversation_id,
        lead_id,
        fecha_inicio as conversation_started_at
    from {{ ref('stg_conversations') }}
)
select
    r.conversation_id,
    c.lead_id,
    c.conversation_started_at,
    r.modelo_interes,
    r.presupuesto,
    r.cuota_inicial,
    r.forma_pago,
    r.intencion,
    r.objecion_principal,
    r.pidio_cita,
    r.pidio_cotizacion,
    r.evidencia,
    r.evidence_grounded,
    r.model_requested,
    r.model_returned,
    r.semantic_prompt_version,
    r.batch_contract_version,
    r.processed_at
from ranked_success r
join conversations c using (conversation_id)
where r.extraction_rank = 1
