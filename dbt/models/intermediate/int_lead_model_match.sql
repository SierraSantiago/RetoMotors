with leads as (
    select * from {{ ref('stg_leads') }}
), catalog as (
    select sku, modelo_canonico, marca_normalizada, linea_normalizada, precio_lista, modelo_normalizado
    from {{ ref('stg_catalogo_motos') }}
), aliases as (
    select alias_normalizado, sku from {{ ref('model_aliases') }}
), fuzzy as (
    select modelo_interes_normalizado, top_1_score, decision, sku
    from {{ ref('model_fuzzy_matches') }}
), resolved as (
    select
        l.*,
        coalesce(exact.sku, alias.sku, case when f.decision = 'MATCHED' then f.sku end) as resolved_sku,
        case
            when l.modelo_interes_normalizado is null or l.modelo_interes_normalizado = '' then 'MISSING'
            when exact.sku is not null then 'MATCHED'
            when alias.sku is not null then 'MATCHED'
            when f.decision is not null then f.decision
            else 'UNMATCHED'
        end as resolved_status,
        case
            when l.modelo_interes_normalizado is null or l.modelo_interes_normalizado = '' then 'none'
            when exact.sku is not null then 'normalized_exact'
            when alias.sku is not null then 'alias'
            when f.decision is not null then 'fuzzy'
            else 'none'
        end as resolved_method,
        case
            when l.modelo_interes_normalizado is null or l.modelo_interes_normalizado = '' then null::numeric
            when exact.sku is not null then 1.0::numeric
            when alias.sku is not null then 1.0::numeric
            else f.top_1_score::numeric
        end as resolved_score
    from leads l
    left join catalog exact on exact.modelo_normalizado = l.modelo_interes_normalizado
    left join aliases alias on alias.alias_normalizado = l.modelo_interes_normalizado
    left join fuzzy f on f.modelo_interes_normalizado = l.modelo_interes_normalizado
)
select
    r.raw_row_id, r.lead_id, r.empresa_id, r.punto_venta_id,
    r.modelo_interes_raw, r.modelo_interes_normalizado,
    c.sku, c.modelo_canonico, c.marca_normalizada, c.linea_normalizada, c.precio_lista,
    r.resolved_method as match_method,
    r.resolved_score as match_score,
    r.resolved_status as match_status,
    case
        when c.sku is null or r.punto_venta_id is null then null::boolean
        else exists (
            select 1
            from {{ ref('int_catalog_availability') }} a
            where a.sku = c.sku and a.punto_venta_id = r.punto_venta_id
        )
    end as is_available_at_store
from resolved r
left join catalog c on c.sku = r.resolved_sku
