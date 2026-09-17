with cross_company as (
    select signal_type, signal_value
    from {{ ref('int_identity_signals') }}
    where signal_type in ('PHONE', 'EMAIL')
    group by signal_type, signal_value
    having count(distinct empresa_id) > 1
), affected as (
    select s.signal_type, s.signal_value, m.customer_identity_id,
           s.empresa_id
    from {{ ref('int_identity_signals') }} s
    join cross_company c using (signal_type, signal_value)
    join {{ ref('int_lead_identity_map') }} m using (raw_row_id)
)
select signal_type, signal_value
from affected
group by signal_type, signal_value, customer_identity_id
having count(distinct empresa_id) > 1
