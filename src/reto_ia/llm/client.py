from langchain_openai import ChatOpenAI

from reto_ia.config import settings
from reto_ia.llm.schema import ConversationExtraction


def build_llm(model: str | None = None) -> ChatOpenAI:
    """Create the direct OpenAI client used by the productive pipeline."""
    selected_model = model or settings.llm_model_primary
    if not selected_model:
        raise ValueError(
            "LLM_MODEL_PRIMARY is not configured. Choose a model before running extraction."
        )

    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not configured.")

    return ChatOpenAI(
        model=selected_model,
        api_key=settings.openai_api_key,
        max_completion_tokens=settings.llm_max_completion_tokens,
        reasoning_effort=settings.llm_reasoning_effort,
        timeout=settings.llm_timeout_seconds,
        max_retries=0,
    )


def build_extraction_llm(model: str | None = None):
    """Return a strict structured-output runnable for one selected model."""

    return build_llm(model).with_structured_output(
        ConversationExtraction,
        method="json_schema",
        strict=True,
        include_raw=True,
    )
