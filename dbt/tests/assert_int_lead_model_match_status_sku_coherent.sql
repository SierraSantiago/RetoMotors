select *
from {{ ref('int_lead_model_match') }}
where (match_status = 'MATCHED' and sku is null)
   or (match_status in ('AMBIGUOUS', 'UNMATCHED', 'MISSING') and sku is not null)
