"""PostgreSQL persistence and checkpoint queries for conversation extraction."""

from collections.abc import Iterable
from typing import Any

from psycopg import Connection
from psycopg.types.json import Jsonb

from reto_ia.llm.persistence import sanitize_postgres_value


def fetch_conversations(
    connection: Connection,
    limit: int | None = None,
    conversation_ids: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    query = """
        select conversacion_id, lead_id, mensajes
        from staging.stg_conversations
        where conversacion_id is not null
        order by conversacion_id
    """
    params: tuple[Any, ...] = ()
    if conversation_ids is not None:
        query = query.replace(
            "where conversacion_id is not null",
            "where conversacion_id is not null and conversacion_id = any(%s)",
        )
        params = (list(conversation_ids),)
    if limit is not None:
        query += " limit %s"
        params += (limit,)
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        return [
            {"conversation_id": row[0], "lead_id": row[1], "mensajes": row[2]}
            for row in cursor.fetchall()
        ]


def fetch_checkpoint(
    connection: Connection,
    *,
    conversation_ids: Iterable[str],
    semantic_prompt_hash: str,
    batch_contract_version: str,
    model_requested: str,
) -> dict[tuple[str, str], dict[str, Any]]:
    ids = list(conversation_ids)
    if not ids:
        return {}
    query = """
        select conversation_id, conversation_hash, status, error_type, error_message
        from ai.conversation_extractions
        where conversation_id = any(%s)
          and semantic_prompt_hash = %s
          and batch_contract_version = %s
          and model_requested = %s
    """
    params = (ids, semantic_prompt_hash, batch_contract_version, model_requested)
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        return {
            (row[0], row[1]): {
                "status": row[2],
                "error_type": row[3],
                "error_message": row[4],
            }
            for row in cursor.fetchall()
        }


def upsert_extractions(connection: Connection, records: list[dict[str, Any]]) -> None:
    if not records:
        return
    columns = (
        "conversation_id", "lead_id", "conversation_hash", "semantic_prompt_version",
        "semantic_prompt_hash", "batch_contract_version", "model_requested", "model_returned",
        "status", "modelo_interes", "presupuesto", "cuota_inicial", "forma_pago", "intencion",
        "objecion_principal", "pidio_cita", "pidio_cotizacion", "evidencia", "evidence_grounded",
        "error_type", "error_message",
    )
    statement = f"""
        insert into ai.conversation_extractions ({', '.join(columns)}, processed_at, updated_at)
        values ({', '.join(['%s'] * len(columns))}, now(), now())
        on conflict (
            conversation_id, conversation_hash, semantic_prompt_hash,
            batch_contract_version, model_requested
        ) do update set
            lead_id = excluded.lead_id,
            semantic_prompt_version = excluded.semantic_prompt_version,
            model_returned = excluded.model_returned,
            status = excluded.status,
            modelo_interes = excluded.modelo_interes,
            presupuesto = excluded.presupuesto,
            cuota_inicial = excluded.cuota_inicial,
            forma_pago = excluded.forma_pago,
            intencion = excluded.intencion,
            objecion_principal = excluded.objecion_principal,
            pidio_cita = excluded.pidio_cita,
            pidio_cotizacion = excluded.pidio_cotizacion,
            evidencia = excluded.evidencia,
            evidence_grounded = excluded.evidence_grounded,
            error_type = excluded.error_type,
            error_message = excluded.error_message,
            processed_at = now(),
            updated_at = now()
    """
    values = []
    for record in records:
        values.append(
            tuple(
                Jsonb(sanitize_postgres_value(record.get(column)))
                if column == "evidencia"
                else sanitize_postgres_value(record.get(column))
                for column in columns
            )
        )
    safe_values = [sanitize_postgres_value(value) for value in values]
    with connection.transaction():
        with connection.cursor() as cursor:
            cursor.executemany(statement, safe_values)
