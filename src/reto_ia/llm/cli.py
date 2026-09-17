"""CLI for checkpoint-aware batch conversation extraction."""

import argparse
import sys

import psycopg

from reto_ia.config import settings
from reto_ia.llm.batch_schema import BATCH_CONTRACT_VERSION
from reto_ia.llm.batch_service import (
    chunked,
    execute_pending,
    plan_cases,
    prepare_cases,
)
from reto_ia.llm.prompting import PROMPT_VERSION
from reto_ia.llm.repository import fetch_conversations


def _print_plan(args: argparse.Namespace, cases, plan) -> None:
    pending = plan["pending"]
    print(f"semantic_prompt_version: {PROMPT_VERSION}")
    print(f"semantic_prompt_hash: {plan['prompt_hash']}")
    print(f"batch_contract_version: {BATCH_CONTRACT_VERSION}")
    print(f"model_requested: {args.model}")
    print("provider: OpenAI")
    print(f"reasoning_effort: {settings.llm_reasoning_effort}")
    print(f"max_completion_tokens: {settings.llm_max_completion_tokens}")
    print("max_retries: 0")
    print(f"batch_size: {args.batch_size}")
    print(f"conversaciones seleccionadas: {len(cases)}")
    print(f"cached successes: {plan['cached']}")
    print(f"existing errors skipped: {plan['existing_errors_skipped']}")
    print(f"pending: {len(pending)}")
    print(f"batches que se ejecutarían: {len(chunked(pending, args.batch_size))}")
    print("conversation_id + conversation_hash:")
    for case in cases:
        print(f"  {case.conversation_id} {case.conversation_hash}")
    print("dry_run: 0 llamadas OpenAI; no se construyó ningún runnable")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Procesamiento batch LLM con checkpoint PostgreSQL"
    )
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--model", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--retry-errors", action="store_true")
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()
    if args.batch_size < 1 or (args.limit is not None and args.limit < 1):
        parser.error("--batch-size y --limit deben ser mayores que cero")
    database_url = args.database_url or settings.database_url
    if not database_url:
        parser.error("DATABASE_URL no está configurada; use --database-url o .env")
    model = args.model or settings.llm_model_primary
    if not model:
        parser.error("LLM_MODEL_PRIMARY no está configurado; use --model")

    try:
        with psycopg.connect(database_url) as connection:
            fetch_limit = None if args.retry_errors and args.limit is not None else args.limit
            cases = prepare_cases(fetch_conversations(connection, fetch_limit))
            plan = plan_cases(connection, cases, model=model, retry_errors=args.retry_errors)
            if args.retry_errors and args.limit is not None:
                cases = plan["pending"][: args.limit]
                plan = plan_cases(connection, cases, model=model, retry_errors=True)
            args.model = model
            if args.dry_run:
                _print_plan(args, cases, plan)
                return 0
            summary = execute_pending(
                connection,
                plan["pending"],
                model=model,
                batch_size=args.batch_size,
                prompt_hash_value=plan["prompt_hash"],
            )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"selected: {len(cases)}")
    print(f"cached: {plan['cached']}")
    print(f"existing_errors_skipped: {plan['existing_errors_skipped']}")
    print(f"pending_initial: {len(plan['pending'])}")
    for key, value in summary.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
