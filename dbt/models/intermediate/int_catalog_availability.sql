with catalog as (
    select * from {{ ref('stg_catalogo_motos') }}
), exploded as (
    select
        c.sku,
        nullif(trim(point_of_sale), '') as punto_venta_id,
        c.raw_row_id,
        c.ingestion_file_id,
        c.source_row_number,
        c.raw_payload,
        c.loaded_at
    from catalog c
    cross join lateral regexp_split_to_table(coalesce(c.puntos_venta_disponibles_raw, ''), '\|') as point_of_sale
)
select distinct
    sku, punto_venta_id, raw_row_id, ingestion_file_id, source_row_number, raw_payload, loaded_at
from exploded
where sku is not null
  and punto_venta_id is not null
