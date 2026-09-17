from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from psycopg import connect
from sklearn.pipeline import Pipeline

from reto_ia.config import settings
from reto_ia.ml.features import prepare_features, serving_query
from reto_ia.ml.repository import fetch_rows, upsert_scores

MODEL_VERSION = "propensity_logistic_v1"


def make_score_rows(
    serving: pd.DataFrame,
    scores: Any,
    training_data_hash: str,
    scored_at: datetime,
) -> list[dict[str, Any]]:
    return [
        {
            "raw_row_id": row.raw_row_id,
            "lead_id": row.lead_id,
            "propensity_score": float(score),
            "model_version": MODEL_VERSION,
            "training_data_hash": training_data_hash,
            "scored_at": scored_at,
        }
        for row, score in zip(serving.itertuples(), scores, strict=True)
    ]


def score_serving_frame(
    pipeline: Pipeline,
    serving: pd.DataFrame,
    training_data_hash: str,
    scored_at: datetime | None = None,
) -> tuple[list[dict[str, Any]], Any]:
    """Run inference only; this function deliberately never calls fit()."""
    scores = pipeline.predict_proba(prepare_features(serving))[:, 1]
    rows = make_score_rows(serving, scores, training_data_hash, scored_at or datetime.now(UTC))
    return rows, scores


def score_current(output_dir: Path, database_url: str | None = None) -> dict[str, Any]:
    db_url = database_url or settings.database_url
    model_path = output_dir / "propensity_model.joblib"
    metadata_path = output_dir / "propensity_metadata.json"
    if not model_path.exists():
        raise FileNotFoundError(f"Propensity model artifact not found: {model_path}")
    if not metadata_path.exists():
        raise FileNotFoundError(f"Propensity metadata not found: {metadata_path}")
    if not db_url:
        raise RuntimeError("DATABASE_URL is required")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    training_data_hash = metadata.get("training_data_hash")
    if not training_data_hash:
        raise ValueError("Propensity metadata has no training_data_hash")
    pipeline = joblib.load(model_path)
    with connect(db_url) as connection:
        serving = pd.DataFrame(fetch_rows(connection, serving_query()))
    score_rows, scores = score_serving_frame(pipeline, serving, training_data_hash)
    with connect(db_url) as connection:
        upsert_scores(connection, score_rows)
    return {
        "model_version": MODEL_VERSION,
        "training_data_hash": training_data_hash,
        "scored_rows": len(score_rows),
        "min_score": float(scores.min()) if len(scores) else None,
        "max_score": float(scores.max()) if len(scores) else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Score current leads with the trained propensity artifact"
    )
    parser.add_argument("--database-url")
    parser.add_argument("--artifact-dir", type=Path, default=Path("artifacts/ml"))
    args = parser.parse_args()
    print(json.dumps(score_current(args.artifact_dir, args.database_url), indent=2))


if __name__ == "__main__":
    main()
