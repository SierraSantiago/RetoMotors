"""Strict contract for extracting commercial signals from a conversation.

The model describes evidence as short verbatim fragments. Evidence is not a
replacement for human review: the evaluator checks the extraction contract,
while the golden set contains independently reviewed labels.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PaymentMethod = Literal["credito", "contado", "no_informa"]
IntentLevel = Literal["alta", "media", "baja", "indeterminada"]
ObjectionType = Literal[
    "precio",
    "cuota",
    "tasa",
    "disponibilidad",
    "modelo",
    "tiempo",
    "documentacion",
    "otra",
]
EvidenceField = Literal[
    "modelo_interes",
    "presupuesto",
    "cuota_inicial",
    "forma_pago",
    "intencion",
    "objecion_principal",
    "pidio_cita",
    "pidio_cotizacion",
]


class ExtractionEvidence(BaseModel):
    """A short auditable quote attributed to the speaker who said it."""

    model_config = ConfigDict(extra="forbid")

    campo: EvidenceField = Field(description="Campo de la extracción que respalda la cita.")
    fragmento: str = Field(
        description="Fragmento breve y textual de la conversación; no debe ser inventado.",
    )
    emisor: Literal["cliente", "asesor"] = Field(
        description="Emisor exacto del fragmento; priorizar citas del cliente."
    )

    @field_validator("fragmento")
    @classmethod
    def validate_fragmento(cls, value: str) -> str:
        if not value.strip() or len(value) > 240:
            raise ValueError("fragmento debe tener entre 1 y 240 caracteres")
        return value


class ConversationExtraction(BaseModel):
    """Version 1 contract for deterministic evaluation of LLM extractions."""

    model_config = ConfigDict(extra="forbid")

    modelo_interes: str | None = Field(
        description=(
            "Modelo explícitamente mencionado como interés del cliente; "
            "null si no hay evidencia."
        ),
    )
    presupuesto: float | None = Field(
        description="Presupuesto expresado por el cliente; null si no informa un valor.",
    )
    cuota_inicial: float | None = Field(
        description="Valor de cuota inicial expresado por el cliente; null si no informa.",
    )
    forma_pago: PaymentMethod = Field(
        description=(
            "credito solo con intención explícita de financiar; contado solo "
            "con pago completo explícito."
        )
    )
    intencion: IntentLevel = Field(
        description="Alta/media/baja según señales comerciales explícitas, no solo el tono."
    )
    objecion_principal: ObjectionType | None = Field(
        description=(
            "Únicamente una objeción explícita: precio, cuota, tasa, "
            "disponibilidad, modelo, tiempo, documentación u otra."
        ),
    )
    pidio_cita: bool = Field(description="True solo si el cliente pide o concreta una cita/visita.")
    pidio_cotizacion: bool = Field(
        description="True solo si el cliente pide una cotización o acepta recibirla explícitamente."
    )
    evidencia: list[ExtractionEvidence] = Field(
        description=(
            "Citas breves y textuales que justifican campos relevantes; "
            "nunca texto inventado."
        ),
    )

    @field_validator("presupuesto", "cuota_inicial")
    @classmethod
    def validate_nonnegative(cls, value: float | None) -> float | None:
        if value is not None and value < 0:
            raise ValueError("los valores monetarios no pueden ser negativos")
        return value
