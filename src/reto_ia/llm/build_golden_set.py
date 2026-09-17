"""Validate human annotations and build the evaluator's reviewed golden set."""

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from reto_ia.llm.prompting import PROMPT_VERSION, prompt_hash

REQUIRED_COLUMNS = {
    "conversation_id",
    "conversation_text",
    "modelo_interes",
    "presupuesto",
    "cuota_inicial",
    "forma_pago",
    "intencion",
    "objecion_principal",
    "pidio_cita",
    "pidio_cotizacion",
    "reviewed",
}


class GoldenReviewRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: str
    conversation_text: str
    modelo_interes: str | None = None
    presupuesto: float | None = None
    cuota_inicial: float | None = None
    forma_pago: str | None = None
    intencion: str | None = None
    objecion_principal: str | None = None
    pidio_cita: bool | None = None
    pidio_cotizacion: bool | None = None
    reviewed: bool

    @field_validator("conversation_id", "conversation_text", mode="before")
    @classmethod
    def required_text(cls, value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("conversation_id y conversation_text son obligatorios")
        return value

    @field_validator(
        "modelo_interes",
        "forma_pago",
        "intencion",
        "objecion_principal",
        mode="before",
    )
    @classmethod
    def blank_to_none(cls, value: Any) -> Any:
        return None if value is None or (isinstance(value, str) and not value.strip()) else value

    @field_validator("presupuesto", "cuota_inicial", mode="before")
    @classmethod
    def nullable_number(cls, value: Any) -> float | None:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return float(value)

    @field_validator("pidio_cita", "pidio_cotizacion", "reviewed", mode="before")
    @classmethod
    def parse_boolean(cls, value: Any) -> bool | None:
        if isinstance(value, bool):
            return value
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
            return value.strip().lower() == "true"
        raise ValueError("booleano inválido; use true o false")

    @field_validator("forma_pago")
    @classmethod
    def valid_payment(cls, value: str | None) -> str | None:
        if value is not None and value not in {"credito", "contado", "no_informa"}:
            raise ValueError("forma_pago inválida")
        return value

    @field_validator("intencion")
    @classmethod
    def valid_intent(cls, value: str | None) -> str | None:
        if value is not None and value not in {"alta", "media", "baja", "indeterminada"}:
            raise ValueError("intencion inválida")
        return value

    @field_validator("objecion_principal")
    @classmethod
    def valid_objection(cls, value: str | None) -> str | None:
        valid = {
            "precio",
            "cuota",
            "tasa",
            "disponibilidad",
            "modelo",
            "tiempo",
            "documentacion",
            "otra",
        }
        if value is not None and value not in valid:
            raise ValueError("objecion_principal inválida")
        return value


def load_review_csv(path: Path) -> list[GoldenReviewRow]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(f"faltan columnas: {', '.join(sorted(missing))}")
        return [GoldenReviewRow.model_validate(row) for row in reader]


def build_golden_payload(rows: list[GoldenReviewRow]) -> dict[str, Any]:
    reviewed = [row for row in rows if row.reviewed]
    return {
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": prompt_hash(),
        "source": "evaluation/golden_review.csv",
        "selection_note": "Solo incluye filas con reviewed=true y etiquetas humanas.",
        "conversations": [
            {
                "conversation_id": row.conversation_id,
                "conversation_text": row.conversation_text,
                "expected": {
                    "modelo_interes": row.modelo_interes,
                    "presupuesto": row.presupuesto,
                    "cuota_inicial": row.cuota_inicial,
                    "forma_pago": row.forma_pago,
                    "intencion": row.intencion,
                    "objecion_principal": row.objecion_principal,
                    "pidio_cita": row.pidio_cita,
                    "pidio_cotizacion": row.pidio_cotizacion,
                    "evidencia": [],
                },
                "reviewed": True,
                "human_review_required": False,
            }
            for row in reviewed
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Construye un golden set solo con filas revisadas por humanos."
    )
    parser.add_argument("--input", type=Path, default=Path("evaluation/golden_review.csv"))
    parser.add_argument("--output", type=Path, default=Path("evaluation/golden_conversations.json"))
    args = parser.parse_args()
    payload = build_golden_payload(load_review_csv(args.input))
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Casos revisados exportados: {len(payload['conversations'])}")


if __name__ == "__main__":
    main()
