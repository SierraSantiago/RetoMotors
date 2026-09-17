with expected as (
    select 'LD-00011' as lead_id, 'EMP-02' as empresa_id
    union all
    select 'LD-00251', 'EMP-03'
), grouped as (
    select m.customer_identity_id, l.empresa_id,
           count(*) as row_count,
           count(distinct l.lead_id) as lead_id_count
    from {{ ref('int_lead_identity_map') }} m
    join {{ ref('stg_leads') }} l using (raw_row_id)
    join expected e on e.lead_id = l.lead_id and e.empresa_id = l.empresa_id
    group by m.customer_identity_id, l.empresa_id
)
select * from grouped
where row_count < 2 or lead_id_count <> 1
