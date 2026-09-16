from dataclasses import dataclass
from pathlib import Path
from typing import Any

from psycopg import Connection

from .hashing import sha256_file
from .readers import (
    CSV_CONTRACTS,
    REQUIRED_FILES,
    SourceRow,
    read_conversations,
    read_csv,
)
from .repository import create_pipeline_run, finish_pipeline_run, load_file

SOURCE_BY_FILE = {
    "leads.csv": "leads",
    "conversaciones.json": "conversations",
    "catalogo_motos.csv": "catalogo_motos",
    "asesores.csv": "asesores",
    "historico_cierres.csv": "historico_cierres",
}


@dataclass
class IngestionSummary:
    run_id: Any
    files_loaded: int = 0
    files_skipped: int = 0
    rows_loaded: int = 0
    results: list[tuple[str, str, int]] | None = None
    status: str = "SUCCEEDED"


def _read(path: Path) -> list[SourceRow]:
    if path.name == "conversaciones.json":
        return list(read_conversations(path))
    return list(read_csv(path, CSV_CONTRACTS[path.name]))


def ingest(input_dir: Path, connection: Connection) -> IngestionSummary:
    run_id = create_pipeline_run(connection, "raw_ingestion")
    summary = IngestionSummary(run_id=run_id, results=[])
    try:
        missing = [name for name in REQUIRED_FILES if not (input_dir / name).is_file()]
        if missing:
            raise FileNotFoundError(f"No se encontraron archivos requeridos: {', '.join(missing)}")

        for file_name in REQUIRED_FILES:
            path = input_dir / file_name
            rows = _read(path)
            status, count = load_file(
                connection,
                run_id=run_id,
                source_name=SOURCE_BY_FILE[file_name],
                source_file_name=file_name,
                file_sha256=sha256_file(path),
                file_size_bytes=path.stat().st_size,
                rows=rows,
            )
            summary.results.append((file_name, status, count))
            if status == "LOADED":
                summary.files_loaded += 1
                summary.rows_loaded += count
            else:
                summary.files_skipped += 1
        finish_pipeline_run(
            connection, run_id, "SUCCEEDED", files_loaded=summary.files_loaded,
            files_skipped=summary.files_skipped, rows_loaded=summary.rows_loaded,
        )
        return summary
    except Exception as exc:
        summary.status = "FAILED"
        try:
            finish_pipeline_run(
                connection, run_id, "FAILED", files_loaded=summary.files_loaded,
                files_skipped=summary.files_skipped, rows_loaded=summary.rows_loaded,
                error_message=str(exc), details={"completed_files": summary.results},
            )
        finally:
            raise
