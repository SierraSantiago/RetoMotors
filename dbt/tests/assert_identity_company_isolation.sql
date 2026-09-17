select customer_identity_id
from {{ ref('int_lead_identity_map') }}
group by customer_identity_id
having count(distinct empresa_id) <> 1
