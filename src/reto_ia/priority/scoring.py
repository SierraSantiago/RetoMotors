from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any


def conversation_component(row: dict[str, Any]) -> tuple[float, list[str]]:
    if not row.get("has_conversation"):
        return 0.0, []
    points = {"alta": 15, "media": 8, "baja": 2, "indeterminada": 0}
    value = float(points.get(row.get("conversation_intencion"), 0))
    reasons: list[str] = []
    if points.get(row.get("conversation_intencion"), 0):
        reasons.append(f"Intención {row['conversation_intencion']}")
    if row.get("conversation_pidio_cita") is True:
        value += 10
        reasons.append("Solicitó cita")
    if row.get("conversation_pidio_cotizacion") is True:
        value += 8
        reasons.append("Solicitó cotización")
    if row.get("conversation_cuota_inicial") is not None and row["conversation_cuota_inicial"] > 0:
        value += 7
        reasons.append("Reportó cuota inicial")
    if row.get("conversation_forma_pago") in {"credito", "contado"}:
        value += 5
        reasons.append("Forma de pago informada")
    return min(value, 45.0), reasons


def sla_component(age_hours: float) -> tuple[float, str | None]:
    if age_hours >= 48:
        return 30.0, "Lead esperando más de 48 h"
    if age_hours >= 24:
        return 20.0, "Lead esperando entre 24 y 48 h"
    if age_hours >= 12:
        return 10.0, "Lead esperando entre 12 y 24 h"
    if age_hours >= 4:
        return 5.0, "Lead esperando entre 4 y 12 h"
    return 0.0, None


def availability_component(value: bool | None) -> tuple[float, str | None]:
    if value is True:
        return 20.0, "Producto disponible"
    if value is None:
        return 8.0, "Disponibilidad desconocida"
    return 0.0, None


def propensity_component(percentile: float | None) -> tuple[float, str | None]:
    if percentile is None:
        return 0.0, None
    if percentile >= 0.8:
        return 5.0, "Propensión histórica en top 20%"
    if percentile >= 0.5:
        return 3.0, "Propensión histórica entre percentiles 50 y 80"
    if percentile >= 0.2:
        return 1.0, "Propensión histórica entre percentiles 20 y 50"
    return 0.0, None


def age_hours(fecha_registro: date | datetime | None, scoring_timestamp: datetime) -> float:
    if fecha_registro is None:
        return 0.0
    if isinstance(fecha_registro, datetime):
        start = fecha_registro
    else:
        start = datetime(fecha_registro.year, fecha_registro.month, fecha_registro.day)
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if scoring_timestamp.tzinfo is None:
        scoring_timestamp = scoring_timestamp.replace(tzinfo=UTC)
    return max(0.0, (scoring_timestamp - start).total_seconds() / 3600)


def temperature(score: float) -> str:
    if score >= 60:
        return "HOT"
    if score >= 35:
        return "WARM"
    return "COLD"


def percentile_map(rows: list[dict[str, Any]]) -> dict[str, float]:
    ordered = sorted(rows, key=lambda row: (row["propensity_score"], str(row["raw_row_id"])))
    denominator = max(len(ordered) - 1, 1)
    return {str(row["raw_row_id"]): index / denominator for index, row in enumerate(ordered)}


def score_rows(rows: list[dict[str, Any]], scoring_timestamp: datetime) -> list[dict[str, Any]]:
    percentiles = percentile_map(rows)
    scored = []
    for row in rows:
        age = age_hours(row.get("fecha_registro"), scoring_timestamp)
        conversation, reasons = conversation_component(row)
        sla, sla_reason = sla_component(age)
        availability, availability_reason = availability_component(row.get("is_available_at_store"))
        percentile = percentiles.get(str(row["raw_row_id"]))
        propensity, propensity_reason = propensity_component(percentile)
        reasons.extend(
            reason for reason in (sla_reason, availability_reason, propensity_reason) if reason
        )
        raw_score = conversation + sla + availability + propensity
        score = round(max(0.0, min(100.0, raw_score)), 2)
        scored.append({
            **row,
            "propensity_percentile": percentile,
            "conversation_component": conversation,
            "sla_component": sla,
            "availability_component": availability,
            "propensity_component": propensity,
            "priority_score": score,
            "temperature": temperature(score),
            "priority_reasons": reasons,
            "lead_age_hours": age,
            "scoring_timestamp": scoring_timestamp,
        })
    return sorted(
        scored,
        key=lambda row: (
            -row["priority_score"], row.get("fecha_registro") is None,
            row.get("fecha_registro"), str(row["raw_row_id"]),
        ),
    )
