with base as (
    select raw_row_id, count(*) as row_count
    from {{ ref('mart_leads_enriched') }}
    group by raw_row_id
), enriched as (
    select raw_row_id, count(*) as row_count
    from {{ ref('mart_leads_ai_enriched') }}
    group by raw_row_id
)
select
    coalesce(b.raw_row_id, e.raw_row_id) as raw_row_id,
    coalesce(b.row_count, 0) as base_row_count,
    coalesce(e.row_count, 0) as enriched_row_count
from base b
full outer join enriched e using (raw_row_id)
where coalesce(b.row_count, 0) <> coalesce(e.row_count, 0)
