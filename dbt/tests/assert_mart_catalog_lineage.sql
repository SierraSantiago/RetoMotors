select
    m.raw_row_id,
    m.sku as mart_sku,
    i.sku as intermediate_sku,
    m.match_status as mart_match_status,
    i.match_status as intermediate_match_status
from {{ ref('mart_leads_enriched') }} m
join {{ ref('int_lead_model_match') }} i using (raw_row_id)
where m.sku is distinct from i.sku
   or m.modelo_canonico is distinct from i.modelo_canonico
   or m.marca_normalizada is distinct from i.marca_normalizada
   or m.linea_normalizada is distinct from i.linea_normalizada
   or m.precio_lista is distinct from i.precio_lista
   or m.match_method is distinct from i.match_method
   or m.match_score is distinct from i.match_score
   or m.match_status is distinct from i.match_status
   or m.is_available_at_store is distinct from i.is_available_at_store
