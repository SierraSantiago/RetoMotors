select customer_identity_id
from {{ ref('mart_leads_enriched') }}
group by customer_identity_id
having count(distinct empresa_id) <> 1
