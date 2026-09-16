with source as (
    select * from {{ source('raw', 'leads') }}
), normalized as (
    select
        raw_row_id, ingestion_file_id, source_row_number, raw_payload, loaded_at,
        lead_id, empresa_id, punto_venta_id, nombre_cliente,
        nullif(trim(canal), '') as canal_raw,
        nullif(trim(estado_gestion), '') as estado_gestion_raw,
        nullif(trim(ciudad), '') as ciudad_raw,
        nullif(trim(telefono), '') as telefono_raw,
        nullif(trim(email), '') as email_raw,
        nullif(trim(modelo_interes_texto), '') as modelo_interes_raw,
        nullif(trim(fecha_registro), '') as fecha_registro_raw,
        nullif(trim(fecha_primer_contacto), '') as fecha_primer_contacto_raw,
        nullif(trim(campania), '') as campania_raw
    from source
)
select
    raw_row_id, ingestion_file_id, source_row_number, raw_payload, loaded_at,
    lead_id, empresa_id, punto_venta_id, nombre_cliente,
    canal_raw,
    case {{ normalize_text('canal_raw') }}
        when 'whatsapp' then 'whatsapp'
        when 'meta ads' then 'meta_ads'
        when 'formulario web' then 'formulario_web'
        else null
    end as canal_normalizado,
    estado_gestion_raw,
    case {{ normalize_text('estado_gestion_raw') }}
        when 'sin gestion' then 'sin_gestion'
        when 'contactado' then 'contactado'
        when 'no contesta' then 'no_contesta'
        when 'cotizacion enviada' then 'cotizacion_enviada'
        when 'en proceso' then 'en_proceso'
        when 'descartado' then 'descartado'
        else null
    end as estado_gestion_normalizado,
    ciudad_raw,
    case {{ normalize_text('ciudad_raw') }}
        when 'bogota' then 'bogota'
        when 'bogota d.c.' then 'bogota'
        when 'bogota dc' then 'bogota'
        when 'medellin' then 'medellin'
        when 'rio negro' then 'rionegro'
        when 'rionegro' then 'rionegro'
        when 'b/quilla' then 'barranquilla'
        when 'barranquilla' then 'barranquilla'
        when 'sta marta' then 'santa_marta'
        when 'santa marta' then 'santa_marta'
        when 'bello' then 'bello'
        when 'cartagena' then 'cartagena'
        when 'cartagena de indias' then 'cartagena'
        when 'itagui' then 'itagui'
        when 'monteria' then 'monteria'
        when 'soacha' then 'soacha'
        when 'soledad' then 'soledad'
        else null
    end as ciudad_normalizada,
    telefono_raw,
    case
        when telefono_raw is null then null
        when regexp_replace(telefono_raw, '[^0-9]', '', 'g') ~ '^3[0-9]{9}$'
            then '+57' || regexp_replace(telefono_raw, '[^0-9]', '', 'g')
        when regexp_replace(telefono_raw, '[^0-9]', '', 'g') ~ '^57(3[0-9]{9})$'
            then '+57' || substring(regexp_replace(telefono_raw, '[^0-9]', '', 'g') from 3)
        when regexp_replace(telefono_raw, '[^0-9]', '', 'g') ~ '^0057(3[0-9]{9})$'
            then '+57' || substring(regexp_replace(telefono_raw, '[^0-9]', '', 'g') from 5)
        else null
    end as telefono_normalizado,
    case
        when telefono_raw is null then 'MISSING'
        when regexp_replace(telefono_raw, '[^0-9]', '', 'g') ~ '^(3[0-9]{9}|57(3[0-9]{9})|0057(3[0-9]{9}))$' then 'VALID'
        else 'INVALID'
    end as telefono_parse_status,
    email_raw,
    {{ normalize_text('email_raw') }} as email_normalizado,
    modelo_interes_raw,
    nullif({{ normalize_lexical('modelo_interes_raw') }}, '') as modelo_interes_normalizado,
    fecha_registro_raw,
    {{ safe_date_value('fecha_registro_raw') }} as fecha_registro,
    {{ safe_date_status('fecha_registro_raw') }} as fecha_registro_parse_status,
    fecha_primer_contacto_raw,
    {{ safe_date_value('fecha_primer_contacto_raw') }} as fecha_primer_contacto,
    {{ safe_date_status('fecha_primer_contacto_raw') }} as fecha_primer_contacto_parse_status,
    campania_raw,
    nullif(trim(campania_raw), '') as campania_normalizada
from normalized
