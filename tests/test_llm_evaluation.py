from pathlib import Path
from types import SimpleNamespace

import pytest

from reto_ia.llm import client as llm_client
from reto_ia.llm import evaluate as evaluation
from reto_ia.llm.build_golden_set import GoldenReviewRow, load_review_csv
from reto_ia.llm.evaluate import (
    calculate_metrics,
    classify_error,
    evaluate_model,
    evidence_is_grounded,
    extract_model_returned,
    load_golden_set,
    normalize_lexical,
)
from reto_ia.llm.prompting import PROMPT_VERSION, load_extraction_prompt, prompt_hash
from reto_ia.llm.schema import ConversationExtraction


def test_extraction_schema_rejects_invalid_enum_and_extra_field():
    with pytest.raises(ValueError):
        ConversationExtraction(
            modelo_interes=None,
            presupuesto=None,
            cuota_inicial=None,
            forma_pago="financiado",
            intencion="alta",
            objecion_principal=None,
            pidio_cita=False,
            pidio_cotizacion=False,
            inesperado=True,
        )


def test_prompt_is_loadable_and_versioned():
    prompt = load_extraction_prompt()
    assert PROMPT_VERSION == "conversation_extraction_v2"
    assert "No inventes" in prompt
    assert '"tengo X para la inicial"' in prompt
    assert 'cuota_inicial=0' in prompt
    assert '"voy esta tarde"' in prompt
    assert len(prompt_hash()) == 64


def test_model_normalization_is_lexical_only():
    assert normalize_lexical(" Honda  CB 190R ") == "honda cb 190r"
    assert normalize_lexical("Honda CB 190R") == normalize_lexical("hónda-cb/190r")


def test_metrics_are_per_field_and_numeric_tolerant():
    results = [
        {
            "status": "ok",
            "latency_seconds": 0.2,
            "expected": {
                "modelo_interes": "Honda CB 190R",
                "presupuesto": 1000,
                "forma_pago": "contado",
                "intencion": "alta",
                "cuota_inicial": None,
                "objecion_principal": None,
                "pidio_cita": True,
                "pidio_cotizacion": False,
            },
            "actual": {
                "modelo_interes": "hónda cb-190r",
                "presupuesto": 1005,
                "forma_pago": "contado",
                "intencion": "media",
                "cuota_inicial": None,
                "objecion_principal": None,
                "pidio_cita": True,
                "pidio_cotizacion": False,
            },
        }
    ]
    metrics = calculate_metrics(results)
    assert metrics["semantic_accuracy_by_field_on_success"]["modelo_interes"]["accuracy"] == 1
    assert metrics["semantic_accuracy_by_field_on_success"]["presupuesto"]["accuracy"] == 1
    assert metrics["semantic_accuracy_by_field_on_success"]["intencion"]["accuracy"] == 0
    assert metrics["semantic_accuracy_by_field_on_success"]["cuota_inicial"]["labeled"] == 1
    assert metrics["semantic_accuracy_by_field_on_success"]["cuota_inicial"]["accuracy"] == 1
    assert metrics["semantic_macro_accuracy_on_success"] == 7 / 8
    assert metrics["mean_latency_seconds"] == 0.2


@pytest.mark.parametrize(
    ("expected", "actual", "correct"),
    [(None, None, 1), (None, 10000000, 0), (10000000, None, 0)],
)
def test_metrics_evaluate_reviewed_nulls(expected, actual, correct):
    metrics = calculate_metrics(
        [
            {
                "expected": {"presupuesto": expected},
                "actual": {"presupuesto": actual},
                "status": "ok",
                "latency_seconds": 0.1,
            }
        ]
    )
    assert metrics["end_to_end_accuracy_by_field"]["presupuesto"]["correct"] == correct
    assert metrics["end_to_end_accuracy_by_field"]["presupuesto"]["labeled"] == 1


def test_model_returned_is_read_from_response_metadata():
    raw = SimpleNamespace(response_metadata={"model_name": "provider/real-model"})
    assert extract_model_returned(raw) == "provider/real-model"
    assert extract_model_returned(SimpleNamespace(response_metadata={})) is None


def test_evidence_grounding_accepts_literal_fragment_and_rejects_invention():
    text = "CLIENTE: Me interesa la moto y puedo pagar de contado."
    assert evidence_is_grounded(
        text,
        {"evidencia": [{"fragmento": "Me interesa la moto", "emisor": "cliente"}]},
    )
    assert not evidence_is_grounded(
        text,
        {"evidencia": [{"fragmento": "Quiero una cita mañana", "emisor": "cliente"}]},
    )


def test_evidence_grounding_normalizes_unicode_case_and_whitespace():
    text = "CLIENTE: Café   mañana"
    fragment = " cliente: cafe\u0301\tMAÑANA "
    assert evidence_is_grounded(
        text,
        {"evidencia": [{"fragmento": fragment, "emisor": "cliente"}]},
    )


def test_metrics_separate_successes_from_end_to_end_failures():
    fields = (
        "modelo_interes",
        "presupuesto",
        "cuota_inicial",
        "forma_pago",
        "intencion",
        "objecion_principal",
        "pidio_cita",
        "pidio_cotizacion",
    )
    expected = {field: None for field in fields}
    successful = {
        "status": "ok",
        "expected": expected,
        "actual": expected,
        "latency_seconds": 0.1,
    }
    failed = {
        "status": "error",
        "error_type": "request_error",
        "expected": expected,
        "latency_seconds": 0.1,
    }
    metrics = calculate_metrics([successful, failed])
    assert metrics["attempted_cases"] == 2
    assert metrics["successful_extractions"] == 1
    assert metrics["success_rate"] == 0.5
    assert metrics["semantic_macro_accuracy_on_success"] == 1
    assert metrics["end_to_end_macro_accuracy"] == 0.5
    assert metrics["structured_output_failures"] == 0


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("404 model not found", "model_unavailable"),
        ("429 rate limit", "rate_limit"),
        ("connection refused", "request_error"),
        ("Could not parse response content as the length limit was reached", "output_length_limit"),
        ("request timed out", "request_timeout"),
        ("parsed=None; parsing_error=None", "structured_output_invalid"),
    ],
)
def test_error_classification(message, expected):
    assert classify_error(RuntimeError(message)) == expected


@pytest.mark.parametrize("error_type", ["output_length_limit", "request_timeout"])
def test_operational_failures_reduce_end_to_end_without_structured_failure(error_type):
    fields = (
        "modelo_interes", "presupuesto", "cuota_inicial", "forma_pago",
        "intencion", "objecion_principal", "pidio_cita", "pidio_cotizacion",
    )
    expected = {field: None for field in fields}
    metrics = calculate_metrics([
        {
            "status": "error",
            "error_type": error_type,
            "expected": expected,
            "latency_seconds": 0.1,
        }
    ])
    assert metrics["success_rate"] == 0
    assert metrics["end_to_end_macro_accuracy"] == 0
    assert metrics["structured_output_failures"] == 0
    assert metrics["errors_by_type"][error_type] == 1


def test_parsed_none_is_classified_without_iterating_none(monkeypatch):
    class FakeRunnable:
        def invoke(self, _prompt):
            return {
                "raw": SimpleNamespace(response_metadata={}),
                "parsed": None,
                "parsing_error": None,
            }

    monkeypatch.setattr(evaluation, "build_extraction_llm", lambda _model: FakeRunnable())
    result = evaluation.evaluate_model(
        "test-model",
        [{"conversation_id": "CONV-1", "conversation_text": "CLIENTE: Hola", "expected": {}}],
    )
    row = result["results"][0]
    assert row["error_type"] == "structured_output_invalid"
    assert "parsed=None" in row["error"]
    assert result["metrics"]["structured_output_failures"] == 1


def test_native_structured_output_configuration(monkeypatch):
    captured = {}

    class FakeLLM:
        def with_structured_output(self, schema, **kwargs):
            captured["schema"] = schema
            captured["kwargs"] = kwargs
            return "runnable"

    monkeypatch.setattr(llm_client, "build_llm", lambda model: FakeLLM())
    assert llm_client.build_extraction_llm("gpt-5-nano") == "runnable"
    assert captured["schema"] is ConversationExtraction
    assert captured["kwargs"] == {
        "method": "json_schema",
        "strict": True,
        "include_raw": True,
    }


def test_openai_client_configuration(monkeypatch):
    monkeypatch.setattr(llm_client.settings, "openai_api_key", "test-key")
    llm = llm_client.build_llm("gpt-5-nano")
    assert getattr(llm, "base_url", None) is None
    assert getattr(llm, "extra_body", None) is None
    assert llm.max_tokens == 16384
    assert llm.reasoning_effort == "minimal"
    assert llm.request_timeout == 90.0
    assert llm.max_retries == 0


def test_csv_parser_loads_35_cases_with_10_reviewed():
    rows = load_review_csv(Path("evaluation/golden_review.csv"))
    assert len(rows) == 35
    assert sum(row.reviewed for row in rows) == 10
    assert sum(not row.reviewed for row in rows) == 25
    assert all(row.conversation_text for row in rows)


@pytest.mark.parametrize(
    ("field", "value"),
    [("forma_pago", "financiado"), ("intencion", "urgente"), ("objecion_principal", "inventada")],
)
def test_golden_review_rejects_invalid_enums(field, value):
    data = {
        "conversation_id": "CONV-TEST",
        "conversation_text": "CLIENTE: Hola",
        "reviewed": "true",
        field: value,
    }
    with pytest.raises(ValueError):
        GoldenReviewRow.model_validate(data)


def test_benchmark_requires_reviewed_golden_labels(tmp_path):
    empty_golden = tmp_path / "empty_golden.json"
    empty_golden.write_text('{"conversations": []}', encoding="utf-8")
    assert load_golden_set(empty_golden) == []
    with pytest.raises(ValueError, match="reviewed=true"):
        evaluate_model("model-for-test", [])
