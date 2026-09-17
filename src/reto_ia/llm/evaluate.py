"""Reproducible, model-by-model evaluation harness for the extraction contract."""

import argparse
import json
import re
import time
import unicodedata
from pathlib import Path
from statistics import mean
from typing import Any

from pydantic import BaseModel

from reto_ia.llm.client import build_extraction_llm
from reto_ia.llm.prompting import PROMPT_VERSION, load_extraction_prompt, prompt_hash

NUMERIC_FIELDS = {"presupuesto", "cuota_inicial"}
CATEGORICAL_FIELDS = {
    "modelo_interes",
    "forma_pago",
    "intencion",
    "objecion_principal",
    "pidio_cita",
    "pidio_cotizacion",
}
MISSING = object()


def normalize_lexical(value: str | None) -> str | None:
    """Normalize model names for comparison without applying catalog matching."""

    if value is None:
        return None
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    normalized = re.sub(r"[^a-zA-Z0-9]+", " ", normalized.lower())
    return " ".join(normalized.split()) or None


def numeric_equal(actual: float | None, expected: float | None) -> bool:
    if actual is None or expected is None:
        return actual is expected
    tolerance = max(0.01, abs(expected) * 0.01)
    return abs(actual - expected) <= tolerance


def field_equal(field: str, actual: Any, expected: Any) -> bool:
    if actual is MISSING:
        return False
    if field == "modelo_interes":
        return normalize_lexical(actual) == normalize_lexical(expected)
    if field in NUMERIC_FIELDS:
        return numeric_equal(actual, expected)
    return actual == expected


def calculate_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Separate semantic quality on successes from end-to-end reliability."""

    fields = sorted(CATEGORICAL_FIELDS | NUMERIC_FIELDS)
    successful = [r for r in results if r.get("status") == "ok"]

    def field_metrics(cases: list[dict[str, Any]]) -> tuple[dict[str, Any], float | None]:
        by_field: dict[str, dict[str, Any]] = {}
        accuracies = []
        for field in fields:
            labeled = [r for r in cases if field in r.get("expected", {})]
            correct = sum(
                field_equal(
                    field,
                    r.get("actual", {}).get(field, MISSING),
                    r["expected"][field],
                )
                for r in labeled
            )
            accuracy = correct / len(labeled) if labeled else None
            by_field[field] = {
                "correct": correct,
                "labeled": len(labeled),
                "accuracy": accuracy,
            }
            if accuracy is not None:
                accuracies.append(accuracy)
        return by_field, mean(accuracies) if accuracies else None

    semantic_by_field, semantic_macro = field_metrics(successful)
    end_to_end_by_field, end_to_end_macro = field_metrics(results)
    attempted = len(results)
    successful_count = len(successful)
    return {
        "attempted_cases": attempted,
        "successful_extractions": successful_count,
        "success_rate": successful_count / attempted if attempted else None,
        "semantic_accuracy_by_field_on_success": semantic_by_field,
        "semantic_macro_accuracy_on_success": semantic_macro,
        "end_to_end_accuracy_by_field": end_to_end_by_field,
        "end_to_end_macro_accuracy": end_to_end_macro,
        "structured_output_failures": sum(
            r.get("error_type") == "structured_output_invalid" for r in results
        ),
        "evidence_grounded": all(
            r.get("evidence_grounded") is True for r in successful
        ) if successful else None,
        "evidence_grounding_failures": sum(
            r.get("evidence_grounded") is False for r in results
        ),
        "mean_latency_seconds": (
            mean(r["latency_seconds"] for r in successful) if successful else None
        ),
        "errors_by_type": {
            error_type: sum(r.get("error_type") == error_type for r in results)
            for error_type in {r.get("error_type") for r in results if r.get("error_type")}
        },
    }


def classify_error(error: Exception) -> str:
    messages = []
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        messages.extend((str(current), repr(current)))
        current = current.__cause__ or current.__context__
    message = " ".join(messages).lower()
    if any(
        marker in message
        for marker in (
            "length limit was reached",
            "maximum completion tokens",
            "max_completion_tokens",
            "max tokens",
            "finish_reason=length",
            '"finish_reason": "length"',
        )
    ):
        return "output_length_limit"
    if "429" in message or "rate limit" in message or "too many requests" in message:
        return "rate_limit"
    if "timeout" in message or "timed out" in message:
        return "request_timeout"
    if "404" in message or "not found" in message or "model" in message and "available" in message:
        return "model_unavailable"
    if any(
        marker in message
        for marker in ("connection", "connecterror", "apierror", "status code: 5")
    ):
        return "request_error"
    return "structured_output_invalid"


class StructuredOutputValidationError(ValueError):
    """Response was received but did not yield the Pydantic extraction."""


def describe_structured_output_error(output: dict[str, Any]) -> str:
    parsing_error = output.get("parsing_error")
    if parsing_error is not None:
        return repr(parsing_error)
    return "parsed=None; parsing_error=None; response did not contain parsed structured output"


def extract_model_returned(raw: Any) -> str | None:
    """Read provider model metadata without guessing when it is absent."""

    sources = [
        getattr(raw, "response_metadata", None),
        getattr(raw, "model_name", None),
        getattr(raw, "model", None),
        getattr(raw, "additional_kwargs", None),
    ]
    for source in sources:
        if isinstance(source, str) and source:
            return source
        if isinstance(source, dict):
            for key in ("model_name", "model"):
                value = source.get(key)
                if isinstance(value, str) and value:
                    return value
    return None


def normalize_evidence_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", " ", normalized).strip()


def evidence_is_grounded(conversation_text: str, actual: dict[str, Any]) -> bool:
    """Require every returned evidence fragment to occur in the source text."""

    source = normalize_evidence_text(conversation_text)
    return all(
        isinstance(item, dict)
        and isinstance(item.get("fragmento"), str)
        and normalize_evidence_text(item["fragmento"]) in source
        for item in actual.get("evidencia") or []
    )


def load_golden_set(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    reviewed = [case for case in payload["conversations"] if case.get("reviewed") is True]
    return reviewed


def evaluate_model(model: str, conversations: list[dict[str, Any]]) -> dict[str, Any]:
    if not conversations:
        raise ValueError("No hay casos de golden set con reviewed=true; benchmark cancelado.")
    runnable = build_extraction_llm(model)
    results = []
    prompt = load_extraction_prompt()
    for case in conversations:
        started = time.perf_counter()
        result: dict[str, Any] = {
            "conversation_id": case["conversation_id"],
            "model_requested": model,
            "expected": case["expected"],
        }
        try:
            output = runnable.invoke(f"{prompt}\n\nCONVERSACIÓN:\n{case['conversation_text']}")
            if isinstance(output, dict) and "parsed" in output:
                parsed = output["parsed"]
                raw = output.get("raw")
                result["model_returned"] = extract_model_returned(raw)
                result["pydantic_validation"] = isinstance(parsed, BaseModel)
                if parsed is None:
                    raise StructuredOutputValidationError(
                        describe_structured_output_error(output)
                    )
                if isinstance(parsed, BaseModel):
                    result["actual"] = parsed.model_dump(mode="json")
                    result["evidence_grounded"] = evidence_is_grounded(
                        case["conversation_text"], result["actual"]
                    )
                else:
                    raise ValueError("structured output no validó contra ConversationExtraction")
            elif isinstance(output, BaseModel):
                result["model_returned"] = None
                result["pydantic_validation"] = True
                result["actual"] = output.model_dump(mode="json")
            else:
                result["model_returned"] = None
                result["pydantic_validation"] = False
                raise ValueError("structured output no validó contra ConversationExtraction")
            result["status"] = "ok"
        except Exception as error:  # noqa: BLE001 - the harness must continue per model/case.
            result.update(
                status="error",
                pydantic_validation=False,
                error_type=classify_error(error),
                error=str(error),
            )
        result["latency_seconds"] = round(time.perf_counter() - started, 4)
        results.append(result)
    return {
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": prompt_hash(),
        "metrics": calculate_metrics(results),
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate extraction models on the reviewed golden set."
    )
    parser.add_argument("--golden-set", type=Path, required=True)
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument(
        "--max-cases",
        type=int,
        help="Limita los casos revisados evaluados; por defecto usa todos.",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    conversations = load_golden_set(args.golden_set)
    if not conversations:
        raise ValueError(
            "No hay ground truth revisado; marque filas reviewed=true antes del benchmark."
        )
    if args.max_cases is not None and args.max_cases < 1:
        raise ValueError("--max-cases debe ser mayor que cero.")
    if args.max_cases is not None:
        conversations = conversations[: args.max_cases]
    report = {
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": prompt_hash(),
        "evaluable_cases": len(conversations),
        "models": [evaluate_model(model, conversations) for model in args.models],
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
