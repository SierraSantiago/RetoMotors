select lead_id, conversation_count
from {{ ref('mart_lead_conversation_features') }}
where conversation_count < 1
