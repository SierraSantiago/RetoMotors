from __future__ import annotations

import argparse
from datetime import UTC, date, datetime
from typing import Any

from psycopg import connect

from reto_ia.config import settings
from reto_ia.priority.assignment import add_ranks, assign_rows
from reto_ia.priority.repository import fetch_advisors, fetch_rows, upsert_assignments
from reto_ia.priority.scoring import score_rows


def build_rows(
    database_url: str, scoring_timestamp: datetime
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    with connect(database_url) as connection:
        rows = fetch_rows(connection)
        advisors = fetch_advisors(connection)
    scored = score_rows(rows, scoring_timestamp)
    return add_ranks(assign_rows(scored, advisors)), advisors


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and assign the daily lead priority list")
    parser.add_argument("--assignment-date", default=date.today().isoformat())
    parser.add_argument("--database-url")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    database_url = args.database_url or settings.database_url
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    scoring_timestamp = datetime.now(UTC)
    rows, advisors = build_rows(database_url, scoring_timestamp)
    if not args.dry_run:
        with connect(database_url) as connection:
            upsert_assignments(connection, rows, args.assignment_date)
    statuses = ("ASSIGNED", "UNASSIGNED_CAPACITY", "NO_ELIGIBLE_ADVISOR")
    counts = {
        status: sum(row["assignment_status"] == status for row in rows)
        for status in statuses
    }
    temperatures = {
        name: sum(row["temperature"] == name for row in rows)
        for name in ("HOT", "WARM", "COLD")
    }
    capacity_used = counts["ASSIGNED"]
    print({
        "dry_run": args.dry_run,
        "assignment_date": args.assignment_date,
        "total_leads": len(rows),
        "temperatures": temperatures,
        "assignment": counts,
        "capacity_used": capacity_used,
        "active_capacity": sum(
            a.get("capacidad_diaria_leads") or 0
            for a in advisors if a.get("activo") is True
        ),
    })


if __name__ == "__main__":
    main()
