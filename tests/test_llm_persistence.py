from types import SimpleNamespace

import pytest

from reto_ia.llm import batch_service
from reto_ia.llm.batch_schema import (
    BatchConversationExtraction,
    BatchConversationExtractionItem,
    TransportExtraction,
)
from reto_ia.llm.conversation import conversation_hash
from reto_ia.llm.persistence import sanitize_postgres_value


def _extraction(evidence=None):
    return TransportExtraction(
        modelo_interes=None,
        presupuesto=None,
        cuota_inicial=None,
        forma_pago="no_informa",
        intencion="indeterminada",
        objecion_principal=None,
        pidio_cita=False,
        pidio_cotizacion=False,
        evidencia=evidence or [],
    )


def _case(identifier):
    text = f"CLIENTE: Hola {identifier}"
    return batch_service.ConversationCase(identifier, None, text, conversation_hash(text))


def test_sanitize_postgres_value_only_removes_real_nul():
    value = {"items": ["abc\x00def", "áéíóú ñ 😀\n\t", "\\u0000"]}
    assert sanitize_postgres_value(value) == {
        "items": ["abcdef", "áéíóú ñ 😀\n\t", "\\u0000"]
    }


def test_normal_conversation_hash_is_unchanged_and_nul_hash_uses_sanitized_text():
    normal = "CLIENTE: Hola"
    assert conversation_hash(normal) == conversation_hash(sanitize_postgres_value(normal))
    dirty = "CLIENTE: Ho\x00la"
    assert conversation_hash(dirty.replace("\x00", "")) == conversation_hash(
        sanitize_postgres_value(dirty)
    )


def test_persistence_failure_is_checkpointed_as_error_for_every_case(monkeypatch):
    cases = [_case("CONV-1"), _case("CONV-2")]
    def item(case):
        return BatchConversationExtractionItem(
            conversation_id=case.conversation_id, extraction=_extraction()
        )
    fake = SimpleNamespace(
        with_structured_output=lambda *args, **kwargs: SimpleNamespace(
            invoke=lambda _prompt: {
                "parsed": BatchConversationExtraction(
                    results=[item(cases[1]), item(cases[0])]
                ),
                "raw": SimpleNamespace(),
            }
        )
    )
    persisted = []

    calls = 0

    def fail_once(_connection, rows):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("db failure\x00")
        persisted.extend(rows)

    monkeypatch.setattr(batch_service, "build_llm", lambda _model: fake)
    monkeypatch.setattr(batch_service, "upsert_extractions", fail_once)
    summary = batch_service.execute_pending(
        object(), cases, model="model", batch_size=16, prompt_hash_value="hash"
    )
    assert summary["successful"] == 0
    assert summary["errors"] == 2
    assert [row["conversation_id"] for row in persisted] == ["CONV-1", "CONV-2"]
    assert all(row["error_type"] == "persistence_error" for row in persisted)
    assert all("\x00" not in row["error_message"] for row in persisted)


def test_failure_to_checkpoint_persistence_error_stops_execution(monkeypatch):
    cases = [_case("CONV-1")]
    batch = BatchConversationExtraction(
        results=[
            BatchConversationExtractionItem(
                conversation_id="CONV-1", extraction=_extraction()
            )
        ]
    )
    fake = SimpleNamespace(
        with_structured_output=lambda *args, **kwargs: SimpleNamespace(
            invoke=lambda _prompt: {"parsed": batch, "raw": SimpleNamespace()}
        )
    )
    monkeypatch.setattr(batch_service, "build_llm", lambda _model: fake)
    monkeypatch.setattr(
        batch_service,
        "upsert_extractions",
        lambda _connection, _rows: (_ for _ in ()).throw(RuntimeError("db failure")),
    )
    with pytest.raises(RuntimeError, match="checkpoint ERROR"):
        batch_service.execute_pending(
            object(), cases, model="model", batch_size=16, prompt_hash_value="hash"
        )
