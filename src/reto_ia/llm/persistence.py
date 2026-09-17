"""Values safe to send through PostgreSQL text and JSON boundaries."""

from collections.abc import Mapping
from typing import Any


def sanitize_postgres_value(value: Any) -> Any:
    """Remove only real NUL characters, preserving all other source content."""

    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, Mapping):
        return {key: sanitize_postgres_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_postgres_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_postgres_value(item) for item in value)
    return value
