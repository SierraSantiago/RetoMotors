with staging_counts as (
    select raw_row_id, count(*) as row_count
    from {{ ref('stg_leads') }}
    group by raw_row_id
), mart_counts as (
    select raw_row_id, count(*) as row_count
    from {{ ref('mart_leads_enriched') }}
    group by raw_row_id
)
select
    coalesce(s.raw_row_id, m.raw_row_id) as raw_row_id,
    coalesce(s.row_count, 0) as staging_row_count,
    coalesce(m.row_count, 0) as mart_row_count
from staging_counts s
full outer join mart_counts m using (raw_row_id)
where coalesce(s.row_count, 0) <> 1
   or coalesce(m.row_count, 0) <> 1
