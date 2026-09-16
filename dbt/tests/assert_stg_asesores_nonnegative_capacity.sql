select *
from {{ ref('stg_asesores') }}
where capacidad_diaria_leads is not null and capacidad_diaria_leads < 0
