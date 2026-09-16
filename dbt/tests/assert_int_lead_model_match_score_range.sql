select *
from {{ ref('int_lead_model_match') }}
where match_score is not null and (match_score < 0 or match_score > 1)
