select lead_id
from {{ ref('mart_leads_enriched') }}
where lead_id in ('LD-00011', 'LD-00251')
group by lead_id
having count(*) <> 2
