from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from psycopg import Connection


def fetch_rows(connection: Connection, query: str) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(query)
        columns = [item.name for item in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def fetch_capacity_share(connection: Connection, current_rows: int) -> float | None:
    if not current_rows:
        return None
    with connection.cursor() as cursor:
        cursor.execute("""
            select coalesce(sum(capacidad_diaria_leads) filter (where activo is true), 0)
            from staging.stg_asesores
        """)
        capacity = cursor.fetchone()[0]
    return float(capacity) / current_rows


def upsert_scores(connection: Connection, rows: Iterable[dict[str, Any]]) -> None:
    values = list(rows)
    if not values:
        return
    statement = """
        insert into ml.lead_propensity_scores
            (raw_row_id, lead_id, propensity_score, model_version,
             training_data_hash, scored_at, updated_at)
        values (%s, %s, %s, %s, %s, %s, now())
        on conflict (raw_row_id, model_version) do update set
            lead_id = excluded.lead_id,
            propensity_score = excluded.propensity_score,
            training_data_hash = excluded.training_data_hash,
            scored_at = excluded.scored_at,
            updated_at = now()
    """
    with connection.transaction():
        with connection.cursor() as cursor:
            cursor.executemany(
                statement,
                [
                    (
                        row["raw_row_id"], row["lead_id"], row["propensity_score"],
                        row["model_version"], row["training_data_hash"], row["scored_at"],
                    )
                    for row in values
                ],
            )

