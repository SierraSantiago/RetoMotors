import argparse
import sys
from pathlib import Path

import psycopg

from ..config import settings
from .service import ingest


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga idempotente de fuentes en RAW")
    parser.add_argument("--input-dir", type=Path, default=Path("data/input"))
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()
    database_url = args.database_url or settings.database_url
    if not database_url:
        parser.error("DATABASE_URL no está configurada; use --database-url o .env")

    try:
        with psycopg.connect(database_url) as connection:
            summary = ingest(args.input_dir, connection)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Pipeline run: {summary.run_id}\n")
    for file_name, status, count in summary.results or []:
        print(f"{file_name:<25} {status:<8} {count:>6}")
    print(f"\nFiles loaded: {summary.files_loaded}")
    print(f"Files skipped: {summary.files_skipped}")
    print(f"Rows loaded: {summary.rows_loaded}")
    print(f"Status: {summary.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
