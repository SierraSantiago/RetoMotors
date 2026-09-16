select *
from {{ ref('stg_historico_cierres') }}
where (desenlace_normalizado = 'cerrado' and is_closed is distinct from true)
   or (desenlace_normalizado = 'perdido' and is_closed is distinct from false)
   or (desenlace_normalizado = 'sin gestion' and is_closed is not null)
