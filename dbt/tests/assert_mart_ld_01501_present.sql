select 'LD-01501' as lead_id
where not exists (
    select 1
    from {{ ref('mart_leads_enriched') }}
    where lead_id = 'LD-01501'
)
