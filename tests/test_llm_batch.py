from types import SimpleNamespace

import pytest

from reto_ia.llm import batch_service
from reto_ia.llm.batch_schema import (
    BATCH_CONTRACT_VERSION,
    BatchConversationExtraction,
    BatchConversationExtractionItem,
    TransportExtraction,
)
from reto_ia.llm.conversation import conversation_hash, render_conversation


def test_batch_transport_json_schema_has_no_untyped_nodes():
    schema = BatchConversationExtraction.model_json_schema()

    def walk(node):
        if isinstance(node, dict):
            if "type" not in node and ("properties" in node or "items" in node):
                return 1
            return sum(walk(value) for value in node.values())
        if isinstance(node, list):
            return sum(walk(value) for value in node)
        return 0

    assert schema["type"] == "object"
    assert schema["properties"]["results"]["type"] == "array"
    item_schema = schema["$defs"]["BatchConversationExtractionItem"]
    assert item_schema["type"] == "object"
    assert schema["properties"]["results"]["items"]["$ref"].endswith(
        "/BatchConversationExtractionItem"
    )
    assert walk(schema) == 0


def make_extraction():
    return TransportExtraction(
        modelo_interes=None, presupuesto=None, cuota_inicial=None,
        forma_pago="no_informa", intencion="indeterminada",
        objecion_principal=None, pidio_cita=False, pidio_cotizacion=False, evidencia=[]
    )


def make_case(conversation_id):
    text = f"CLIENTE: Hola {conversation_id}"
    return batch_service.ConversationCase(
        conversation_id, f"LD-{conversation_id}", text, conversation_hash(text)
    )


def test_conversation_hash_is_deterministic_and_speaker_ordered():
    messages = [
        {"emisor": "cliente", "texto": "Hola"},
        {"emisor": "asesor", "texto": "Â¿En quÃ© puedo ayudarle?"},
    ]
    rendered = render_conversation(messages)
    assert rendered == "CLIENTE: Hola\nASESOR: Â¿En quÃ© puedo ayudarle?"
    assert conversation_hash(rendered) == conversation_hash(rendered)
    assert conversation_hash(rendered) != conversation_hash(rendered.replace("Hola", "AdiÃ³s"))


def test_batch_transport_accepts_extra_evidence_for_item_normalization():
    extraction = TransportExtraction(
        **make_extraction().model_dump(exclude={"evidencia"}),
        evidencia=[{"campo": "intencion", "fragmento": "uno", "emisor": "cliente"}] * 3,
    )
    item = BatchConversationExtractionItem(conversation_id="CONV-1", extraction=extraction)
    assert len(batch_service.normalize_transport_extraction(item.extraction).evidencia) == 2


def test_fragment_is_truncated_and_empty_evidence_is_dropped():
    payload = make_extraction().model_dump()
    payload["evidencia"] = [
        {"campo": "intencion", "fragmento": "   ", "emisor": "cliente"},
        {"campo": "intencion", "fragmento": "x" * 300, "emisor": "cliente"},
    ]
    normalized = batch_service.normalize_transport_extraction(payload)
    assert len(normalized.evidencia) == 1
    assert normalized.evidencia[0].fragmento == "x" * 240


def _run_fake_batch(monkeypatch, cases, parsed):
    monkeypatch.setattr(
        batch_service, "build_llm",
        lambda _model: SimpleNamespace(
            with_structured_output=lambda *args, **kwargs: SimpleNamespace(
                invoke=lambda _prompt: {"parsed": parsed, "raw": SimpleNamespace()}
            )
        ),
    )
    persisted = []
    monkeypatch.setattr(
        batch_service, "upsert_extractions", lambda _c, rows: persisted.extend(rows)
    )
    summary = batch_service.execute_pending(
        object(), cases, model="model", batch_size=16, prompt_hash_value="hash"
    )
    return persisted, summary


def test_execution_invokes_once_and_matches_results_by_id(monkeypatch):
    cases = [make_case("CONV-1"), make_case("CONV-2")]
    parsed = BatchConversationExtraction(results=[
        BatchConversationExtractionItem(conversation_id="CONV-2", extraction=make_extraction()),
        BatchConversationExtractionItem(conversation_id="CONV-1", extraction=make_extraction()),
    ])
    fake = SimpleNamespace(calls=0)
    def invoke(_prompt):
        fake.calls += 1
        return {"parsed": parsed, "raw": SimpleNamespace()}
    monkeypatch.setattr(batch_service, "build_llm", lambda _model: SimpleNamespace(
        with_structured_output=lambda *args, **kwargs: SimpleNamespace(invoke=invoke)))
    persisted = []
    monkeypatch.setattr(
        batch_service, "upsert_extractions", lambda _c, rows: persisted.extend(rows)
    )
    summary = batch_service.execute_pending(
        object(), cases, model="model", batch_size=16, prompt_hash_value="hash"
    )
    assert fake.calls == 1
    assert summary["llm_requests_attempted"] == 1
    assert [row["conversation_id"] for row in persisted] == ["CONV-1", "CONV-2"]
    assert all(row["status"] == "SUCCESS" for row in persisted)
    assert BATCH_CONTRACT_VERSION == "conversation_extraction_batch_v1"


def test_semantic_invalid_value_is_rejected_after_transport():
    payload = make_extraction().model_dump()
    payload["forma_pago"] = "invalid"
    with pytest.raises(ValueError):
        batch_service.normalize_transport_extraction(payload)


def test_duplicate_missing_and_unexpected_ids_are_item_scoped(monkeypatch):
    cases = [make_case(cid) for cid in ["A", "B", "C", "D"]]
    extraction = make_extraction().model_dump()
    parsed = BatchConversationExtraction(results=[
        BatchConversationExtractionItem(conversation_id=cid, extraction=extraction)
        for cid in ["A", "B", "B", "D", "X"]
    ])
    persisted, _ = _run_fake_batch(monkeypatch, cases, parsed)
    assert [row["conversation_id"] for row in persisted] == ["A", "B", "C", "D"]
    assert [row["status"] for row in persisted] == ["SUCCESS", "ERROR", "ERROR", "SUCCESS"]
    assert persisted[1]["error_type"] == "duplicate_response_id"
    assert persisted[2]["error_type"] == "missing_response_id"


@pytest.mark.parametrize("retry_errors, expected_pending", [(False, 0), (True, 1)])
def test_checkpoint_skips_success_and_retries_errors_only_when_requested(
    monkeypatch, retry_errors, expected_pending
):
    case = make_case("CONV-1")
    monkeypatch.setattr(batch_service, "fetch_checkpoint", lambda _connection, **_kwargs: {
        (case.conversation_id, case.conversation_hash): {
            "status": "ERROR", "error_type": "request_timeout", "error_message": "timeout"
        }
    })
    plan = batch_service.plan_cases(object(), [case], model="model", retry_errors=retry_errors)
    assert len(plan["pending"]) == expected_pending
    assert plan["cached"] == 0
    assert plan["existing_errors_skipped"] == (0 if retry_errors else 1)
