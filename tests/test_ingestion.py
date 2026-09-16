import json
from hashlib import sha256

import pytest

from reto_ia.ingestion.hashing import sha256_file
from reto_ia.ingestion.readers import (
    CSV_CONTRACTS,
    validate_conversations_contract,
    validate_csv_contract,
)
from reto_ia.ingestion.service import ingest


def write_all_sources(directory):
    for filename, columns in CSV_CONTRACTS.items():
        row = ",".join(["x"] * len(columns))
        content = ",".join(columns) + "\n" + row + "\n"
        if filename == "leads.csv":
            content += row + "\n"
        (directory / filename).write_text(content, encoding="utf-8")
    conversation = {
        "conversacion_id": "c1", "lead_id": "l1", "canal": "web",
        "fecha_inicio": "x", "mensajes": [],
    }
    (directory / "conversaciones.json").write_text(
        json.dumps([conversation]),
        encoding="utf-8",
    )


def test_sha256_is_deterministic(tmp_path):
    path = tmp_path / "source.bin"
    content = b"raw bytes\x00\xff"
    path.write_bytes(content)
    assert sha256_file(path) == sha256(content).hexdigest()
    assert sha256_file(path) == sha256_file(path)


def test_csv_contract_requires_columns(tmp_path):
    path = tmp_path / "leads.csv"
    path.write_text("lead_id\n1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="faltan columnas"):
        validate_csv_contract(path, CSV_CONTRACTS["leads.csv"])


def test_conversations_contract_requires_list_messages(tmp_path):
    path = tmp_path / "conversaciones.json"
    path.write_text(json.dumps([{
        "conversacion_id": "c1", "lead_id": "l1", "canal": "web",
        "fecha_inicio": "x", "mensajes": {},
    }]), encoding="utf-8")
    with pytest.raises(ValueError, match="debe ser una lista"):
        validate_conversations_contract(path)


def test_ingestion_missing_file_fails_before_reading(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("reto_ia.ingestion.service.create_pipeline_run", lambda *_: "run")
    monkeypatch.setattr(
        "reto_ia.ingestion.service.finish_pipeline_run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    with pytest.raises(FileNotFoundError):
        ingest(tmp_path, object())
    assert calls[0][0][2] == "FAILED"


def test_duplicate_rows_are_not_collapsed_and_same_hash_is_skipped(tmp_path, monkeypatch):
    write_all_sources(tmp_path)
    rows_seen = []
    monkeypatch.setattr("reto_ia.ingestion.service.create_pipeline_run", lambda *_: "run")
    monkeypatch.setattr(
        "reto_ia.ingestion.service.finish_pipeline_run", lambda *args, **kwargs: None
    )

    def fake_load(*args, **kwargs):
        rows = kwargs["rows"]
        rows_seen.append((kwargs["source_name"], len(rows)))
        return ("SKIPPED", 0) if len(rows_seen) > 5 else ("LOADED", len(rows))

    monkeypatch.setattr("reto_ia.ingestion.service.load_file", fake_load)
    first = ingest(tmp_path, object())
    second = ingest(tmp_path, object())
    assert first.files_loaded == 5
    assert second.files_skipped == 5
    assert sum(count for name, count in rows_seen[:5] if name == "leads") == 2
