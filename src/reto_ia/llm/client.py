from langchain_openai import ChatOpenAI

from reto_ia.config import settings


def build_llm(model: str | None = None) -> ChatOpenAI:
    """Create the project LLM client through OpenRouter's OpenAI-compatible API.

    Stage 4 will add structured output, prompt versioning, retries and evaluation.
    """
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
    )
