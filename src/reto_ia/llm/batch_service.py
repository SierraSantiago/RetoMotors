"""Sequential batch extraction, planning and checkpoint-aware execution."""

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from reto_ia.llm.batch_schema import (
    BATCH_CONTRACT_VERSION,
    BatchConversationExtraction,
)
from reto_ia.llm.client import build_llm
from reto_ia.llm.conversation import conversation_hash, render_conversation
from reto_ia.llm.evaluate import (
    classify_error,
    describe_structured_output_error,
    evidence_is_grounded,
    extract_model_returned,
)
from reto_ia.llm.persistence import sanitize_postgres_value
from reto_ia.llm.prompting import PROMPT_VERSION, load_extraction_prompt, prompt_hash
from reto_ia.llm.repository import fetch_checkpoint, upsert_extractions
from reto_ia.llm.schema import ConversationExtraction


@dataclass(frozen=True)
class ConversationCase:
    conversation_id: str
    lead_id: str | None
    canonical_text: str
    conversation_hash: str


def prepare_cases(rows: list[dict[str, Any]]) -> list[ConversationCase]:
    cases = []
    for row in rows:
        canonical_text = render_conversation(row["mensajes"])
        cases.append(
            ConversationCase(
                conversation_id=str(row["conversation_id"]),
                lead_id=row.get("lead_id"),
                canonical_text=canonical_text,
                conversation_hash=conversation_hash(canonical_text),
            )
        )
    return sorted(cases, key=lambda case: case.conversation_id)


def chunked(cases: list[ConversationCase], batch_size: int) -> list[list[ConversationCase]]:
    if batch_size < 1:
        raise ValueError("batch_size debe ser mayor que cero.")
    return [cases[index : index + batch_size] for index in range(0, len(cases), batch_size)]


def build_batch_prompt(cases: list[ConversationCase]) -> str:
    sections = [
        load_extraction_prompt(),
        """
## Contrato de transporte batch

Devuelve exclusivamente structured output válido según el schema recibido.
Devuelve exactamente un resultado por cada conversation_id recibido.
No inventes IDs, no uses la posición de la respuesta para identificar casos y
no incluyas texto fuera del structured output. Cada extracción puede incluir
como máximo 2 evidencias breves, literales y atribuidas al emisor correcto.
""".strip(),
    ]
    for case in cases:
        sections.append(
            f"CONVERSATION_ID: {case.conversation_id}\nCONVERSACIÓN:\n{case.canonical_text}"
        )
    return "\n\n".join(sections)


def normalize_transport_extraction(raw: Any) -> ConversationExtraction:
    """Limit batch evidence, then validate the semantic extraction item."""

    payload = raw.model_dump(mode="json") if isinstance(raw, BaseModel) else raw
    if not isinstance(payload, Mapping):
        raise ValueError("la extracción del item no es un objeto JSON")
    payload = sanitize_postgres_value(dict(payload))
    evidence = payload.get("evidencia")
    normalized_evidence = []
    if isinstance(evidence, list):
        for item in evidence:
            if not isinstance(item, Mapping):
                continue
            fragment = item.get("fragmento")
            if not isinstance(fragment, str):
                continue
            fragment = fragment[:240]
            if not fragment.strip():
                continue
            evidence_item = dict(item)
            evidence_item["fragmento"] = fragment
            normalized_evidence.append(evidence_item)
    payload["evidencia"] = normalized_evidence[:2]
    return ConversationExtraction.model_validate(payload)


def _empty_record(case: ConversationCase, model: str, p_hash: str) -> dict[str, Any]:
    return {
        "conversation_id": case.conversation_id,
        "lead_id": case.lead_id,
        "conversation_hash": case.conversation_hash,
        "semantic_prompt_version": PROMPT_VERSION,
        "semantic_prompt_hash": p_hash,
        "batch_contract_version": BATCH_CONTRACT_VERSION,
        "model_requested": model,
        "model_returned": None,
        "status": "ERROR",
        "modelo_interes": None,
        "presupuesto": None,
        "cuota_inicial": None,
        "forma_pago": None,
        "intencion": None,
        "objecion_principal": None,
        "pidio_cita": None,
        "pidio_cotizacion": None,
        "evidencia": None,
        "evidence_grounded": None,
        "error_type": None,
        "error_message": None,
    }


def _item_error_record(
    case: ConversationCase,
    model: str,
    p_hash: str,
    error_type: str,
    message: str,
) -> dict[str, Any]:
    record = _empty_record(case, model, p_hash)
    record.update(error_type=error_type, error_message=sanitize_postgres_value(message[:2000]))
    return record


def _success_record(
    case: ConversationCase,
    model: str,
    p_hash: str,
    extraction: BaseModel,
    model_returned: str | None,
) -> dict[str, Any]:
    values = sanitize_postgres_value(extraction.model_dump(mode="json"))
    record = _empty_record(case, model, p_hash)
    record.update(
        status="SUCCESS",
        model_returned=model_returned,
        modelo_interes=values["modelo_interes"],
        presupuesto=values["presupuesto"],
        cuota_inicial=values["cuota_inicial"],
        forma_pago=values["forma_pago"],
        intencion=values["intencion"],
        objecion_principal=values["objecion_principal"],
        pidio_cita=values["pidio_cita"],
        pidio_cotizacion=values["pidio_cotizacion"],
        evidencia=values["evidencia"],
        evidence_grounded=evidence_is_grounded(case.canonical_text, values),
    )
    return record


def plan_cases(
    connection: Any,
    cases: list[ConversationCase],
    *,
    model: str,
    retry_errors: bool,
) -> dict[str, Any]:
    p_hash = prompt_hash()
    checkpoint = fetch_checkpoint(
        connection,
        conversation_ids=[case.conversation_id for case in cases],
        semantic_prompt_hash=p_hash,
        batch_contract_version=BATCH_CONTRACT_VERSION,
        model_requested=model,
    )
    pending = []
    cached = 0
    existing_errors_skipped = 0
    for case in cases:
        state = checkpoint.get((case.conversation_id, case.conversation_hash))
        if state and state["status"] == "SUCCESS":
            cached += 1
        elif state and state["status"] == "ERROR" and not retry_errors:
            existing_errors_skipped += 1
        else:
            pending.append(case)
    return {
        "prompt_hash": p_hash,
        "pending": pending,
        "cached": cached,
        "existing_errors_skipped": existing_errors_skipped,
    }


def execute_pending(
    connection: Any,
    pending: list[ConversationCase],
    *,
    model: str,
    batch_size: int,
    prompt_hash_value: str,
) -> dict[str, int]:
    runnable = build_llm(model).with_structured_output(
        BatchConversationExtraction,
        method="json_schema",
        strict=True,
        include_raw=True,
    )
    summary = {"batches_attempted": 0, "llm_requests_attempted": 0, "successful": 0, "errors": 0}
    for batch in chunked(pending, batch_size):
        summary["batches_attempted"] += 1
        records = []
        batch_successes = 0
        batch_errors = 0
        try:
            summary["llm_requests_attempted"] += 1
            output = runnable.invoke(build_batch_prompt(batch))
            parsed = output.get("parsed") if isinstance(output, dict) else output
            if not isinstance(parsed, BatchConversationExtraction):
                if isinstance(output, dict):
                    raise ValueError(describe_structured_output_error(output))
                raise ValueError("structured output no validó contra BatchConversationExtraction")
            model_returned = (
                extract_model_returned(output.get("raw"))
                if isinstance(output, dict)
                else None
            )
            expected_ids = [case.conversation_id for case in batch]
            counts = Counter(item.conversation_id for item in parsed.results)
            by_id = {item.conversation_id: item for item in parsed.results}
            for case in batch:
                response_id = case.conversation_id
                if counts[response_id] > 1:
                    records.append(
                        _item_error_record(
                            case,
                            model,
                            prompt_hash_value,
                            "duplicate_response_id",
                            "El modelo devolvió el conversation_id más de una vez.",
                        )
                    )
                elif response_id not in by_id:
                    records.append(
                        _item_error_record(
                            case,
                            model,
                            prompt_hash_value,
                            "missing_response_id",
                            "No se recibió resultado para el conversation_id esperado.",
                        )
                    )
                else:
                    try:
                        extraction = normalize_transport_extraction(
                            by_id[response_id].extraction
                        )
                    except Exception as item_error:  # noqa: BLE001 - isolate item failures.
                        records.append(
                            _item_error_record(
                                case,
                                model,
                                prompt_hash_value,
                                "structured_output_invalid",
                                str(item_error),
                            )
                        )
                    else:
                        records.append(
                            _success_record(
                                case,
                                model,
                                prompt_hash_value,
                                extraction,
                                model_returned,
                            )
                        )
            # Unexpected IDs are intentionally not persisted. Any affected
            # expected IDs are already represented as missing_response_id.
            _ = set(counts) - set(expected_ids)
            batch_successes = sum(record["status"] == "SUCCESS" for record in records)
            batch_errors = len(records) - batch_successes
        except Exception as error:  # noqa: BLE001 - persist and continue with next batch.
            error_type = (
                "batch_contract_invalid"
                if str(error).startswith("batch_contract_invalid")
                else classify_error(error)
            )
            message = str(error)[:2000]
            records = [
                _item_error_record(case, model, prompt_hash_value, error_type, message)
                for case in batch
            ]
            batch_errors = len(records)
        try:
            upsert_extractions(connection, records)
        except Exception as persistence_error:  # noqa: BLE001 - checkpoint handling boundary.
            if all(record["status"] == "ERROR" for record in records):
                raise RuntimeError(
                    "No se pudo persistir el checkpoint ERROR del batch. "
                    "La ejecución se detiene para no perder el estado."
                ) from persistence_error
            error_message = sanitize_postgres_value(str(persistence_error)[:2000])
            error_records = []
            for case in batch:
                record = _empty_record(case, model, prompt_hash_value)
                record.update(error_type="persistence_error", error_message=error_message)
                error_records.append(record)
            try:
                upsert_extractions(connection, error_records)
            except Exception as checkpoint_error:  # noqa: BLE001 - must stop on lost checkpoint.
                raise RuntimeError(
                    "No se pudo persistir el checkpoint ERROR del batch. "
                    "La ejecución se detiene para no perder el estado."
                ) from checkpoint_error
            summary["errors"] += len(error_records)
            continue
        summary["successful"] += batch_successes
        summary["errors"] += batch_errors
    return summary
