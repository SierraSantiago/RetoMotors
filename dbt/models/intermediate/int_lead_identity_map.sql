with recursive
leads as (
    select raw_row_id, lead_id, empresa_id, canal_normalizado,
           telefono_normalizado, email_normalizado
    from {{ ref('stg_leads') }}
), signals as (
    select * from {{ ref('int_identity_signals') }}
), edges as (
    select distinct
        left_signal.empresa_id,
        left_signal.raw_row_id as from_row_id,
        right_signal.raw_row_id as to_row_id
    from signals as left_signal
    join signals as right_signal
      on right_signal.empresa_id = left_signal.empresa_id
     and right_signal.signal_type = left_signal.signal_type
     and right_signal.signal_value = left_signal.signal_value
     and right_signal.raw_row_id <> left_signal.raw_row_id
), reachability(root_row_id, raw_row_id, empresa_id) as (
    select raw_row_id, raw_row_id, empresa_id from leads
    union
    select reachability.root_row_id, edges.to_row_id, edges.empresa_id
    from reachability
    join edges
      on edges.from_row_id = reachability.raw_row_id
     and edges.empresa_id = reachability.empresa_id
), components as (
    select raw_row_id, empresa_id, min(root_row_id::text)::uuid as component_key
    from reachability
    group by raw_row_id, empresa_id
), component_signals as (
    select
        components.component_key,
        components.empresa_id,
        signals.signal_type,
        signals.signal_value
    from components
    join signals
      on signals.raw_row_id = components.raw_row_id
     and signals.empresa_id = components.empresa_id
), component_identity as (
    select
        component_key,
        empresa_id,
        'CID_' || md5(
            empresa_id || '|' || coalesce(
                min(signal_value) filter (where signal_type = 'PHONE'),
                min(signal_value) filter (where signal_type = 'EMAIL'),
                min(signal_value) filter (where signal_type = 'SOURCE_LEAD_ID')
            )
        ) as customer_identity_id,
        jsonb_build_object(
            'signal_types', coalesce(
                jsonb_agg(distinct signal_type order by signal_type), '[]'::jsonb
            ),
            'signal_value_hashes', coalesce(
                jsonb_agg(distinct jsonb_build_object(
                    'signal_type', signal_type,
                    'value_hash', md5(signal_value)
                ) order by jsonb_build_object(
                    'signal_type', signal_type,
                    'value_hash', md5(signal_value)
                )), '[]'::jsonb
            )
        ) as identity_evidence
    from component_signals
    group by component_key, empresa_id
), component_members as (
    select
        components.component_key,
        count(*) as identity_member_count,
        count(distinct leads.lead_id) as distinct_lead_id_count,
        count(distinct leads.canal_normalizado) as distinct_channel_count
    from components
    join leads using (raw_row_id, empresa_id)
    group by components.component_key
)
select
    leads.raw_row_id,
    leads.lead_id,
    leads.empresa_id,
    component_identity.customer_identity_id,
    component_members.identity_member_count,
    component_members.identity_member_count > 1 as is_duplicate_identity,
    component_members.identity_member_count > component_members.distinct_lead_id_count
        as is_source_duplicate,
    component_identity.identity_evidence,
    component_members.distinct_channel_count > 1 as has_multiple_channels
from components
join leads using (raw_row_id, empresa_id)
join component_identity using (component_key, empresa_id)
join component_members using (component_key)
