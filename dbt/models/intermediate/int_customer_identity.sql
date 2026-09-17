with mapped as (
    select * from {{ ref('int_lead_identity_map') }}
), leads as (
    select raw_row_id, lead_id, empresa_id, canal_normalizado,
           telefono_normalizado, email_normalizado
    from {{ ref('stg_leads') }}
)
select
    mapped.customer_identity_id,
    mapped.empresa_id,
    count(*) as lead_count,
    count(distinct leads.lead_id) as distinct_lead_id_count,
    count(distinct leads.canal_normalizado) as distinct_channel_count,
    count(distinct leads.telefono_normalizado) filter (
        where leads.telefono_normalizado is not null
    ) as phone_count,
    count(distinct leads.email_normalizado) filter (
        where leads.email_normalizado is not null
    ) as email_count,
    count(distinct leads.canal_normalizado) > 1 as has_multiple_channels,
    count(*) > count(distinct leads.lead_id) as has_source_duplicate,
    array_agg(distinct leads.lead_id order by leads.lead_id)
        filter (where leads.lead_id is not null) as lead_ids,
    array_agg(distinct leads.canal_normalizado order by leads.canal_normalizado)
        filter (where leads.canal_normalizado is not null) as channels,
    (array_agg(mapped.identity_evidence order by mapped.raw_row_id))[1]
        as identity_evidence
from mapped
join leads on leads.raw_row_id = mapped.raw_row_id
group by mapped.customer_identity_id, mapped.empresa_id
