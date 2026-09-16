select sku, punto_venta_id
from {{ ref('int_catalog_availability') }}
group by sku, punto_venta_id
having count(*) > 1
