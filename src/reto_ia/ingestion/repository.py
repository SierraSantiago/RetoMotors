from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

RAW_COLUMNS = {
    "leads": [
        "lead_id", "fecha_registro", "canal", "empresa_id", "punto_venta_id",
        "nombre_cliente", "telefono", "email", "ciudad", "modelo_interes_texto",
        "estado_gestion", "fecha_primer_contacto", "campania",
    ],
    "conversations": ["conversacion_id", "lead_id", "canal", "fecha_inicio", "mensajes"],
    "catalogo_motos": [
        "sku", "marca", "linea", "cilindraje", "segmento", "precio_lista",
        "puntos_venta_disponibles", "unidades_disponibles",
    ],
    "asesores": [
        "asesor_id", "nombre", "punto_venta_id", "empresa_id",
        "capacidad_diaria_leads", "activo", "fecha_ingreso",
    ],
    "historico_cierres": [
        "lead_id", "fecha_registro", "canal", "empresa_id", "punto_venta_id",
        "modelo_cotizado", "precio_lista", "horas_al_primer_contacto",
        "numero_contactos", "manifesto_cuota_inicial", "forma_pago_declarada",
        "pidio_cita", "desenlace",
    ],
}


def create_pipeline_run(connection: Connection, pipeline_name: str) -> UUID:
    with connection.cursor() as cursor:
        cursor.execute(
            """insert into ops.pipeline_runs (pipeline_name, status, started_at)
               values (%s, 'RUNNING', %s) returning run_id""",
            (pipeline_name, datetime.now(UTC)),
        )
        run_id = cursor.fetchone()[0]
    connection.commit()
    return run_id


def finish_pipeline_run(connection: Connection, run_id: UUID, status: str, **fields: Any) -> None:
    assignments = ["status = %s", "finished_at = %s"]
    values: list[Any] = [status, datetime.now(UTC)]
    for name in ("files_loaded", "files_skipped", "rows_loaded", "error_message", "details"):
        if name in fields:
            assignments.append(f"{name} = %s")
            values.append(fields[name])
    values.append(run_id)
    with connection.cursor() as cursor:
        cursor.execute(
            f"update ops.pipeline_runs set {', '.join(assignments)} where run_id = %s",
            values,
        )
    connection.commit()


def load_file(
    connection: Connection,
    *,
    run_id: UUID,
    source_name: str,
    source_file_name: str,
    file_sha256: str,
    file_size_bytes: int,
    rows: Sequence[Any],
) -> tuple[str, int]:
    """Load one file in a single transaction; return LOADED/SKIPPED and row count."""
    table_columns = RAW_COLUMNS[source_name]
    with connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute(
                """select ingestion_file_id, status, row_count
                   from ops.ingestion_files
                   where source_name = %s and file_sha256 = %s
                   for update""",
                (source_name, file_sha256),
            )
            existing = cursor.fetchone()
            if existing and existing[1] == "LOADED":
                return "SKIPPED", 0

            if existing:
                ingestion_file_id = existing[0]
                cursor.execute(
                    """update ops.ingestion_files
                       set first_ingested_run_id = %s, source_file_name = %s,
                           file_size_bytes = %s, status = 'LOADING',
                           row_count = null, error_message = null
                       where ingestion_file_id = %s""",
                    (run_id, source_file_name, file_size_bytes, ingestion_file_id),
                )
            else:
                cursor.execute(
                    """insert into ops.ingestion_files
                       (first_ingested_run_id, source_name, source_file_name,
                        file_sha256, file_size_bytes, status)
                       values (%s, %s, %s, %s, %s, 'LOADING')
                       returning ingestion_file_id""",
                    (run_id, source_name, source_file_name, file_sha256, file_size_bytes),
                )
                ingestion_file_id = cursor.fetchone()[0]

            column_sql = ", ".join(
                table_columns + ["ingestion_file_id", "source_row_number", "raw_payload"]
            )
            placeholders = ", ".join(["%s"] * (len(table_columns) + 3))
            statement = f"insert into raw.{source_name} ({column_sql}) values ({placeholders})"
            values = [
                tuple(
                    Jsonb(row.values[column]) if column == "mensajes" else row.values[column]
                    for column in table_columns
                )
                + (ingestion_file_id, row.source_row_number, Jsonb(row.raw_payload))
                for row in rows
            ]
            cursor.executemany(statement, values)
            count = len(values)
            cursor.execute(
                """update ops.ingestion_files
                   set row_count = %s, status = 'LOADED', ingested_at = now()
                   where ingestion_file_id = %s""",
                (count, ingestion_file_id),
            )
    return "LOADED", count
