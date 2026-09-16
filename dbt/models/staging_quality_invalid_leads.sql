{{ config(materialized='view', schema='staging') }}
select *
from {{ ref('stg_leads') }}
where telefono_parse_status = 'INVALID'
   or fecha_registro_parse_status = 'INVALID'
   or fecha_primer_contacto_parse_status = 'INVALID'
   or canal_normalizado is null and canal_raw is not null
   or estado_gestion_normalizado is null and estado_gestion_raw is not null
