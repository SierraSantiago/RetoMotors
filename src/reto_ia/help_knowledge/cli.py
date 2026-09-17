from __future__ import annotations

import argparse
from pathlib import Path

import psycopg

from reto_ia.config import settings
from reto_ia.help_knowledge.loader import markdown_chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="Carga la documentación de ayuda en Supabase.")
    parser.add_argument("--knowledge-dir", type=Path, default=Path("knowledge/help"))
    args = parser.parse_args()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL no está definida.")
    files = sorted(args.knowledge_dir.glob("*.md"))
    if not files:
        raise RuntimeError(f"No hay documentos Markdown en {args.knowledge_dir}.")
    rows = [chunk for path in files for chunk in markdown_chunks(path)]
    statement = """
        insert into app.help_knowledge (slug, title, section, content)
        values (%s, %s, %s, %s)
        on conflict (slug) do update set
            title = excluded.title,
            section = excluded.section,
            content = excluded.content,
            updated_at = now()
    """
    with psycopg.connect(settings.database_url) as connection:
        with connection.cursor() as cursor:
            cursor.executemany(
                statement,
                [(row["slug"], row["title"], row["section"], row["content"]) for row in rows],
            )
    print(f"help knowledge chunks loaded={len(rows)}")


if __name__ == "__main__":
    main()

