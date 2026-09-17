"""Loading and fingerprinting of the versioned extraction prompt."""

import hashlib
from pathlib import Path

PROMPT_VERSION = "conversation_extraction_v3"
PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / f"{PROMPT_VERSION}.md"


def load_extraction_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def prompt_hash() -> str:
    return hashlib.sha256(load_extraction_prompt().encode("utf-8")).hexdigest()
