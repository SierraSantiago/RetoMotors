select
    m.raw_row_id,
    m.customer_identity_id as mart_customer_identity_id,
    i.customer_identity_id as intermediate_customer_identity_id,
    m.empresa_id as mart_empresa_id,
    i.empresa_id as intermediate_empresa_id
from {{ ref('mart_leads_enriched') }} m
join {{ ref('int_lead_identity_map') }} i using (raw_row_id)
where m.customer_identity_id <> i.customer_identity_id
   or m.empresa_id <> i.empresa_id
