from langchain_openai import ChatOpenAI

from reto_ia.config import settings
from reto_ia.llm.schema import ConversationExtraction


def build_llm(model: str | None = None) -> ChatOpenAI:
    """Create a model-specific OpenRouter client without hidden fallbacks."""
    selected_model = model or settings.llm_model_primary
    if not selected_model:
        raise ValueError(
            "LLM_MODEL_PRIMARY is not configured. "
            "Choose a concrete OpenRouter model before running LLM extraction."
        )

    if not settings.openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY is not configured.")

    return ChatOpenAI(
        model=selected_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.llm_base_url,
        temperature=0,
        max_completion_tokens=settings.llm_max_completion_tokens,
        timeout=settings.llm_timeout_seconds,
        extra_body={"provider": {"require_parameters": True}},
    )


def build_extraction_llm(model: str | None = None):
    """Return a strict structured-output runnable for one selected model."""

    return build_llm(model).with_structured_output(
        ConversationExtraction,
        method="json_schema",
        strict=True,
        include_raw=True,
    )
