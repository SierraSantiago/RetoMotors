from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from psycopg import Connection
from psycopg.types.json import Jsonb


def fetch_rows(connection: Connection) -> list[dict[str, Any]]:
    query = """
        select
            l.raw_row_id, l.lead_id, l.empresa_id, l.punto_venta_id,
            l.fecha_registro, l.is_available_at_store,
            l.has_conversation, l.conversation_intencion,
            l.conversation_pidio_cita, l.conversation_pidio_cotizacion,
            l.conversation_cuota_inicial, l.conversation_forma_pago,
            p.propensity_score
        from marts.mart_leads_ai_enriched l
        left join ml.lead_propensity_scores p
          on p.raw_row_id = l.raw_row_id
         and p.model_version = 'propensity_logistic_v1'
        order by l.raw_row_id
    """
    with connection.cursor() as cursor:
        cursor.execute(query)
        columns = [item.name for item in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def fetch_advisors(connection: Connection) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute("""
            select asesor_id, empresa_id, punto_venta_id, activo, capacidad_diaria_leads
            from staging.stg_asesores
            order by asesor_id
        """)
        columns = [item.name for item in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def upsert_assignments(
    connection: Connection, rows: Iterable[dict[str, Any]], assignment_date: str
) -> None:
    columns = (
        "assignment_date", "raw_row_id", "lead_id", "empresa_id", "punto_venta_id",
        "priority_score", "global_priority_rank", "store_priority_rank", "temperature",
        "priority_reasons", "propensity_score", "propensity_percentile", "propensity_component",
        "conversation_component", "sla_component", "availability_component", "advisor_id",
        "assignment_status", "lead_age_hours", "scoring_timestamp",
    )
    statement = f"""
        insert into ops.daily_lead_assignments ({', '.join(columns)})
        values ({', '.join(['%s'] * len(columns))})
        on conflict (assignment_date, raw_row_id) do update set
            lead_id=excluded.lead_id, empresa_id=excluded.empresa_id,
            punto_venta_id=excluded.punto_venta_id, priority_score=excluded.priority_score,
            global_priority_rank=excluded.global_priority_rank,
            store_priority_rank=excluded.store_priority_rank, temperature=excluded.temperature,
            priority_reasons=excluded.priority_reasons, propensity_score=excluded.propensity_score,
            propensity_percentile=excluded.propensity_percentile,
            propensity_component=excluded.propensity_component,
            conversation_component=excluded.conversation_component,
            sla_component=excluded.sla_component,
            availability_component=excluded.availability_component,
            advisor_id=excluded.advisor_id, assignment_status=excluded.assignment_status,
            lead_age_hours=excluded.lead_age_hours, scoring_timestamp=excluded.scoring_timestamp,
            updated_at=now()
    """
    values = []
    for row in rows:
        values.append(tuple(
            Jsonb(row["priority_reasons"]) if column == "priority_reasons" else
            row.get(column) if column not in {"assignment_date"} else assignment_date
            for column in columns
        ))
    with connection.transaction():
        with connection.cursor() as cursor:
            cursor.executemany(statement, values)
