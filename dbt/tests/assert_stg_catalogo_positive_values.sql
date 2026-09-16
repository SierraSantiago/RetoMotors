select *
from {{ ref('stg_catalogo_motos') }}
where (precio_lista is not null and precio_lista <= 0)
   or (unidades_disponibles is not null and unidades_disponibles < 0)
