from __future__ import annotations

import re
from pathlib import Path


def markdown_chunks(path: Path) -> list[dict[str, str]]:
    """Turn a small help document into deterministic, heading-scoped chunks."""
    text = path.read_text(encoding="utf-8").strip()
    sections: list[dict[str, str]] = []
    current_title = path.stem.replace("_", " ").title()
    current_lines: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^#{1,2}\s+(.+?)\s*$", line)
        if match:
            if current_lines and "\n".join(current_lines).strip():
                sections.append(
                    {"title": current_title, "content": "\n".join(current_lines).strip()}
                )
            current_title = match.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines and "\n".join(current_lines).strip():
        sections.append({"title": current_title, "content": "\n".join(current_lines).strip()})
    return [
        {
            "slug": f"{path.stem}-{index:02d}",
            "title": item["title"],
            "section": path.stem,
            "content": item["content"],
        }
        for index, item in enumerate(sections, start=1)
    ]
