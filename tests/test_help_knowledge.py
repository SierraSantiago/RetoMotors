from pathlib import Path

from reto_ia.help_knowledge.loader import markdown_chunks


def test_help_documents_are_heading_scoped_and_deterministic() -> None:
    chunks = markdown_chunks(Path("knowledge/help/03_priority.md"))
    assert chunks
    assert chunks[0]["slug"] == "03_priority-01"
    assert "45" in chunks[0]["content"]


def test_help_topics_cover_retrieval_contract() -> None:
    root = Path("knowledge/help")
    corpus = "\n".join(path.read_text(encoding="utf-8") for path in sorted(root.glob("*.md")))
    assert "prioridad" in corpus.lower()
    assert "respondido" in corpus.lower()
    assert "ROC-AUC" in corpus
    assert "WhatsApp" in corpus

