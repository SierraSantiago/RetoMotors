"""Typed transport contract for batch extraction.

Semantic validation is intentionally performed per item after transport
parsing, while the transport itself remains a valid explicit JSON Schema.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from reto_ia.llm.schema import (
    EvidenceField,
    IntentLevel,
    ObjectionType,
    PaymentMethod,
)

BATCH_CONTRACT_VERSION = "conversation_extraction_batch_v1"


class TransportEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campo: EvidenceField
    fragmento: str
    emisor: Literal["cliente", "asesor"]


class TransportExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modelo_interes: str | None
    presupuesto: float | None
    cuota_inicial: float | None
    forma_pago: PaymentMethod
    intencion: IntentLevel
    objecion_principal: ObjectionType | None
    pidio_cita: bool
    pidio_cotizacion: bool
    evidencia: list[TransportEvidence]


class BatchConversationExtractionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: str
    extraction: TransportExtraction


class BatchConversationExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    results: list[BatchConversationExtractionItem]
