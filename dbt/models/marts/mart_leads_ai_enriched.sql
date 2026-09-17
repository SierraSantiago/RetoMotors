{{ config(materialized='table') }}

select
    l.*,
    (c.lead_id is not null) as has_conversation,
    coalesce(c.conversation_count, 0) as conversation_count,
    (c.lead_id is not null) as has_llm_extraction,
    c.conversation_ids,
    c.first_conversation_at,
    c.latest_conversation_at,
    c.latest_conversation_id,
    c.modelo_interes as conversation_modelo_interes,
    c.presupuesto as conversation_presupuesto,
    c.cuota_inicial as conversation_cuota_inicial,
    c.forma_pago as conversation_forma_pago,
    c.intencion as conversation_intencion,
    c.objecion_principal as conversation_objecion_principal,
    c.pidio_cita as conversation_pidio_cita,
    c.pidio_cotizacion as conversation_pidio_cotizacion,
    c.conversation_evidence_grounded_all,
    c.conversation_evidence_grounded_count,
    c.conversation_evidence_not_grounded_count
from {{ ref('mart_leads_enriched') }} l
left join {{ ref('mart_lead_conversation_features') }} c using (lead_id)
