with source as (
    select * from {{ source('raw', 'catalogo_motos') }}
)
select
    raw_row_id, ingestion_file_id, source_row_number, raw_payload, loaded_at,
    sku,
    nullif(trim(marca), '') as marca_raw,
    nullif({{ normalize_text('marca') }}, '') as marca_normalizada,
    nullif(trim(linea), '') as linea_raw,
    nullif({{ normalize_lexical('linea') }}, '') as linea_normalizada,
    case when nullif(trim(marca), '') is null or nullif(trim(linea), '') is null then null
         else trim(marca) || ' ' || trim(linea) end as modelo_canonico,
    nullif(trim({{ normalize_lexical("coalesce(marca, '') || ' ' || coalesce(linea, '')") }}), '') as modelo_normalizado,
    nullif(trim(cilindraje), '') as cilindraje_raw,
    case when trim(cilindraje) ~ '^[0-9]+$' then trim(cilindraje)::integer else null end as cilindraje,
    case when trim(cilindraje) ~ '^\\d+$' then 'VALID' when nullif(trim(cilindraje), '') is null then 'MISSING' else 'INVALID' end as cilindraje_parse_status,
    nullif(trim(segmento), '') as segmento_raw,
    nullif({{ normalize_text('segmento') }}, '') as segmento_normalizado,
    nullif(trim(precio_lista), '') as precio_lista_raw,
    case when trim(precio_lista) ~ '^[0-9]+(\\.[0-9]+)?$' then trim(precio_lista)::numeric else null end as precio_lista,
    case when trim(precio_lista) ~ '^\\d+(\\.\\d+)?$' then 'VALID' when nullif(trim(precio_lista), '') is null then 'MISSING' else 'INVALID' end as precio_lista_parse_status,
    nullif(trim(puntos_venta_disponibles), '') as puntos_venta_disponibles_raw,
    nullif(trim(unidades_disponibles), '') as unidades_disponibles_raw,
    case when trim(unidades_disponibles) ~ '^[0-9]+$' then trim(unidades_disponibles)::integer else null end as unidades_disponibles,
    case when trim(unidades_disponibles) ~ '^\\d+$' then 'VALID' when nullif(trim(unidades_disponibles), '') is null then 'MISSING' else 'INVALID' end as unidades_disponibles_parse_status
from source
