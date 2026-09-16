with source as (
    select * from {{ source('raw', 'conversations') }}
)
select
    raw_row_id, ingestion_file_id, source_row_number, raw_payload, loaded_at,
    conversacion_id, lead_id,
    nullif(trim(canal), '') as canal_raw,
    case {{ normalize_text('canal') }}
        when 'whatsapp' then 'whatsapp'
        when 'meta ads' then 'meta_ads'
        when 'formulario web' then 'formulario_web'
        else null
    end as canal_normalizado,
    nullif(trim(fecha_inicio), '') as fecha_inicio_raw,
    {{ safe_date_value('fecha_inicio') }} as fecha_inicio,
    {{ safe_date_status('fecha_inicio') }} as fecha_inicio_parse_status,
    mensajes
from source
