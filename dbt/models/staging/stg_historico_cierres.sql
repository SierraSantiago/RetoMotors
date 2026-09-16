with source as (
    select *, nullif(trim(fecha_registro), '') as fecha_registro_raw
    from {{ source('raw', 'historico_cierres') }}
)
select
    raw_row_id, ingestion_file_id, source_row_number, raw_payload, loaded_at,
    lead_id, fecha_registro_raw, {{ safe_date_value('fecha_registro_raw') }} as fecha_registro,
    {{ safe_date_status('fecha_registro_raw') }} as fecha_registro_parse_status,
    nullif(trim(canal), '') as canal_raw,
    case {{ normalize_text('canal') }}
        when 'whatsapp' then 'whatsapp'
        when 'meta ads' then 'meta_ads'
        when 'formulario web' then 'formulario_web'
        else null
    end as canal_normalizado,
    empresa_id, punto_venta_id,
    nullif(trim(modelo_cotizado), '') as modelo_cotizado_raw,
    nullif({{ normalize_lexical('modelo_cotizado') }}, '') as modelo_cotizado_normalizado,
    nullif(trim(precio_lista), '') as precio_lista_raw,
    case when trim(precio_lista) ~ '^[0-9]+(\\.[0-9]+)?$' then trim(precio_lista)::numeric else null end as precio_lista,
    nullif(trim(horas_al_primer_contacto), '') as horas_al_primer_contacto_raw,
    case when trim(horas_al_primer_contacto) ~ '^[0-9]+(\\.[0-9]+)?$' then trim(horas_al_primer_contacto)::numeric else null end as horas_al_primer_contacto,
    nullif(trim(numero_contactos), '') as numero_contactos_raw,
    case when trim(numero_contactos) ~ '^[0-9]+$' then trim(numero_contactos)::integer else null end as numero_contactos,
    nullif(trim(forma_pago_declarada), '') as forma_pago_declarada_raw,
    nullif({{ normalize_text('forma_pago_declarada') }}, '') as forma_pago_declarada_normalizada,
    nullif(trim(manifesto_cuota_inicial), '') as manifesto_cuota_inicial_raw,
    case {{ normalize_text('manifesto_cuota_inicial') }} when 'si' then true when 'no' then false else null end as manifesto_cuota_inicial,
    nullif(trim(pidio_cita), '') as pidio_cita_raw,
    case {{ normalize_text('pidio_cita') }} when 'si' then true when 'no' then false else null end as pidio_cita,
    nullif(trim(desenlace), '') as desenlace_raw,
    nullif({{ normalize_text('desenlace') }}, '') as desenlace_normalizado,
    case {{ normalize_text('desenlace') }} when 'cerrado' then true when 'perdido' then false when 'sin gestion' then null else null end as is_closed
from source
