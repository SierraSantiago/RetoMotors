{{ config(materialized='table') }}

with leads as (
    select *
    from {{ ref('stg_leads') }}
), identity_map as (
    select
        raw_row_id,
        customer_identity_id,
        identity_member_count,
        is_duplicate_identity,
        has_multiple_channels
    from {{ ref('int_lead_identity_map') }}
), model_match as (
    select
        raw_row_id,
        sku,
        modelo_canonico,
        marca_normalizada,
        linea_normalizada,
        precio_lista,
        match_method,
        match_score,
        match_status,
        is_available_at_store
    from {{ ref('int_lead_model_match') }}
)
select
    l.raw_row_id,
    l.lead_id,
    i.customer_identity_id,
    l.empresa_id,
    l.punto_venta_id,

    i.identity_member_count,
    i.is_duplicate_identity,
    i.has_multiple_channels,

    l.nombre_cliente,
    l.telefono_raw,
    l.telefono_normalizado,
    l.telefono_parse_status,
    l.email_raw,
    l.email_normalizado,
    l.ciudad_raw,
    l.ciudad_normalizada,

    l.canal_raw,
    l.canal_normalizado,
    l.fecha_registro_raw,
    l.fecha_registro,
    l.fecha_registro_parse_status,
    l.estado_gestion_raw,
    l.estado_gestion_normalizado,
    l.fecha_primer_contacto_raw,
    l.fecha_primer_contacto,
    l.fecha_primer_contacto_parse_status,
    l.campania_raw,
    l.campania_normalizada,

    l.modelo_interes_raw,
    l.modelo_interes_normalizado,
    m.sku,
    m.modelo_canonico,
    m.marca_normalizada,
    m.linea_normalizada,
    m.precio_lista,
    m.match_method,
    m.match_score,
    m.match_status,
    m.is_available_at_store,

    l.raw_row_id is not null and l.telefono_parse_status = 'VALID'
        as has_valid_phone,
    m.match_status = 'MATCHED' as has_resolved_model,
    l.fecha_registro_parse_status = 'AMBIGUOUS'
        as has_ambiguous_registration_date,

    l.ingestion_file_id,
    l.source_row_number,
    l.loaded_at
from leads l
left join identity_map i using (raw_row_id)
left join model_match m using (raw_row_id)
