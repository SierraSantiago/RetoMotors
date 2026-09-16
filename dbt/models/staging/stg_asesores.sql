with source as (
    select * from {{ source('raw', 'asesores') }}
)
select
    raw_row_id, ingestion_file_id, source_row_number, raw_payload, loaded_at,
    asesor_id, nombre, punto_venta_id, empresa_id,
    nullif(trim(capacidad_diaria_leads), '') as capacidad_diaria_leads_raw,
    case when trim(capacidad_diaria_leads) ~ '^[0-9]+$' then trim(capacidad_diaria_leads)::integer else null end as capacidad_diaria_leads,
    case when trim(capacidad_diaria_leads) ~ '^[0-9]+$' then 'VALID' when nullif(trim(capacidad_diaria_leads), '') is null then 'MISSING' else 'INVALID' end as capacidad_diaria_leads_parse_status,
    nullif(trim(activo), '') as activo_raw,
    case {{ normalize_text('activo') }} when 'si' then true when 'no' then false else null end as activo,
    case when activo is null then 'MISSING' when {{ normalize_text('activo') }} in ('si', 'no') then 'VALID' else 'INVALID' end as activo_parse_status,
    nullif(trim(fecha_ingreso), '') as fecha_ingreso_raw,
    {{ safe_date_value('fecha_ingreso') }} as fecha_ingreso,
    {{ safe_date_status('fecha_ingreso') }} as fecha_ingreso_parse_status
from source
