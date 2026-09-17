from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
from prefect import flow, get_run_logger, task

from reto_ia.config import settings


def _run_command(command: list[str], label: str) -> None:
    logger = get_run_logger()
    logger.info("Starting %s: %s", label, " ".join(command))
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.stdout:
        logger.info("%s stdout:\n%s", label, result.stdout.rstrip())
    if result.stderr:
        logger.warning("%s stderr:\n%s", label, result.stderr.rstrip())
    if result.returncode:
        raise RuntimeError(f"{label} failed with exit code {result.returncode}")
    logger.info("Finished %s", label)


def _module_command(module: str, *args: str) -> list[str]:
    return [sys.executable, "-m", module, *args]


@task(name="source-ingestion", retries=0)
def source_ingestion(input_dir: str) -> None:
    _run_command(
        _module_command("reto_ia.ingestion.cli", "--input-dir", input_dir),
        "source ingestion",
    )


@task(name="dbt-conversation-staging", retries=0)
def dbt_conversation_staging(project_dir: str, profiles_dir: str) -> None:
    _run_command(
        _module_command(
            "dbt.cli.main", "build", "--project-dir", project_dir,
            "--profiles-dir", profiles_dir, "--select", "stg_conversations",
        ),
        "dbt conversation staging",
    )


@task(name="pending-conversation-extraction", retries=0)
def pending_conversation_extraction(batch_size: int) -> None:
    _run_command(
        _module_command(
            "reto_ia.llm.cli", "--batch-size", str(batch_size),
            "--model", settings.llm_model_primary,
        ),
        "pending conversation extraction",
    )


@task(name="dbt-full-build", retries=0)
def dbt_full_build(project_dir: str, profiles_dir: str) -> None:
    _run_command(
        _module_command(
            "dbt.cli.main", "build", "--project-dir", project_dir,
            "--profiles-dir", profiles_dir,
        ),
        "dbt full build",
    )


@task(name="propensity-inference", retries=0)
def propensity_inference(artifact_dir: str) -> dict[str, Any]:
    from reto_ia.ml.scoring import score_current

    result = score_current(Path(artifact_dir))
    get_run_logger().info("Propensity inference scored %s rows", result["scored_rows"])
    return result


@task(name="daily-priority-assignment", retries=0)
def daily_priority_assignment(assignment_date: str) -> None:
    _run_command(
        _module_command("reto_ia.priority.cli", "--assignment-date", assignment_date),
        "daily priority and assignment",
    )


@task(name="operational-validation", retries=0)
def operational_validation(assignment_date: str) -> dict[str, int]:
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required for operational validation")
    checks: dict[str, int] = {}
    with psycopg.connect(settings.database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "select count(*) from ops.daily_lead_assignments "
                "where assignment_date = %s",
                (assignment_date,),
            )
            checks["assignment_rows"] = cursor.fetchone()[0]
            cursor.execute("select count(*) from marts.mart_leads_ai_enriched")
            checks["mart_rows"] = cursor.fetchone()[0]
            cursor.execute(
                "select count(*) from ops.daily_lead_assignments "
                "where assignment_date = %s and (priority_score < 0 or priority_score > 100)",
                (assignment_date,),
            )
            checks["scores_out_of_range"] = cursor.fetchone()[0]
            cursor.execute("""
                select count(*) from ops.daily_lead_assignments d
                left join staging.stg_asesores a on a.asesor_id = d.advisor_id
                where d.assignment_date = %s and d.assignment_status = 'ASSIGNED'
                  and (a.asesor_id is null or a.activo is not true)
            """, (assignment_date,))
            checks["inactive_assignments"] = cursor.fetchone()[0]
            cursor.execute("""
                select count(*) from (
                    select d.advisor_id
                    from ops.daily_lead_assignments d
                    join staging.stg_asesores a on a.asesor_id = d.advisor_id
                    where d.assignment_date = %s and d.assignment_status = 'ASSIGNED'
                    group by d.advisor_id, a.capacidad_diaria_leads
                    having count(*) > coalesce(a.capacidad_diaria_leads, 0)
                ) over_capacity
            """, (assignment_date,))
            checks["advisors_over_capacity"] = cursor.fetchone()[0]
            cursor.execute("""
                select count(*) from ops.daily_lead_assignments d
                join staging.stg_asesores a on a.asesor_id = d.advisor_id
                where d.assignment_date = %s and d.assignment_status = 'ASSIGNED'
                  and (d.empresa_id is distinct from a.empresa_id
                       or d.punto_venta_id is distinct from a.punto_venta_id)
            """, (assignment_date,))
            checks["invalid_company_store_assignments"] = cursor.fetchone()[0]
    checks["row_count_mismatch"] = int(checks["assignment_rows"] != checks["mart_rows"])
    failures = {key: value for key, value in checks.items() if value}
    if failures:
        raise RuntimeError(f"Operational validation failed: {failures}")
    get_run_logger().info("Operational validation passed: %s", checks)
    return checks


@flow(name="reto-motors-daily-pipeline", log_prints=False)
def run_daily_pipeline(
    input_dir: str = "data/input",
    assignment_date: str | None = None,
    artifact_dir: str = "artifacts/ml",
    dbt_project_dir: str = "dbt",
    dbt_profiles_dir: str = "dbt",
    llm_batch_size: int = 16,
) -> dict[str, Any]:
    operational_date = assignment_date or date.today().isoformat()
    source_ingestion(input_dir)
    dbt_conversation_staging(dbt_project_dir, dbt_profiles_dir)
    pending_conversation_extraction(llm_batch_size)
    dbt_full_build(dbt_project_dir, dbt_profiles_dir)
    propensity = propensity_inference(artifact_dir)
    daily_priority_assignment(operational_date)
    validation = operational_validation(operational_date)
    return {"assignment_date": operational_date, "propensity": propensity, "validation": validation}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ejecuta el pipeline diario secuencial de RetoMotors"
    )
    parser.add_argument("--input-dir", default="data/input")
    parser.add_argument("--assignment-date", default=None)
    parser.add_argument("--artifact-dir", default="artifacts/ml")
    parser.add_argument("--dbt-project-dir", default="dbt")
    parser.add_argument("--dbt-profiles-dir", default="dbt")
    parser.add_argument("--llm-batch-size", type=int, default=16)
    args = parser.parse_args()
    run_daily_pipeline(**vars(args))


if __name__ == "__main__":
    main()
