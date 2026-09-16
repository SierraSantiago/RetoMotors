select *
from {{ ref('stg_leads') }}
where punto_venta_id is not null
  and punto_venta_id !~ '^PV-[0-9]{3}$'
