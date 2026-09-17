{{ config(materialized='view') }}

select
    c.conversation_id,
    c.lead_id,
    c.conversation_started_at
from {{ ref('int_conversation_extractions_current') }} c
where c.lead_id is null
   or not exists (
       select 1
       from {{ ref('stg_leads') }} l
       where l.lead_id = c.lead_id
   )
