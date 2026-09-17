"""Canonical conversation rendering and hashing."""

import hashlib
from collections.abc import Iterable, Mapping
from typing import Any

from reto_ia.llm.persistence import sanitize_postgres_value


def render_conversation(messages: Iterable[Mapping[str, Any]]) -> str:
    """Render messages in source order with an explicit speaker label."""

    rendered = []
    for message in messages:
        if not isinstance(message, Mapping):
            raise ValueError("Cada mensaje debe ser un objeto JSON.")
        emitter = str(message.get("emisor", "")).strip().upper()
        text = message.get("texto")
        if not emitter or not isinstance(text, str):
            raise ValueError("Cada mensaje debe tener emisor y texto.")
        rendered.append(f"{emitter}: {sanitize_postgres_value(text)}")
    return "\n".join(rendered)


def conversation_hash(canonical_text: str) -> str:
    return hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()
