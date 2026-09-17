with signals as (
    select * from {{ ref('int_identity_signals') }}
), cross_company as (
    select signal_type, signal_value,
           count(distinct empresa_id) as company_count,
           count(*) as lead_count
    from signals
    where signal_type in ('PHONE', 'EMAIL')
    group by signal_type, signal_value
    having count(distinct empresa_id) > 1
)
select signal_type, md5(signal_value) as signal_value_hash,
       company_count, lead_count
from cross_company
