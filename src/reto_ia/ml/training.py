from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from psycopg import connect
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from reto_ia.config import settings
from reto_ia.ml.evaluation import evaluate_predictions, ranking_metrics
from reto_ia.ml.features import (
    CONTRACT,
    EXCLUDED_FEATURES,
    LEAKAGE_AUDIT,
    prepare_features,
    serving_query,
    training_query,
)
from reto_ia.ml.repository import fetch_capacity_share, fetch_rows, upsert_scores
from reto_ia.ml.scoring import MODEL_VERSION, score_serving_frame


def build_pipeline() -> Pipeline:
    numeric = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    categorical = Pipeline([
        ("imputer", SimpleImputer(strategy="constant", fill_value="__missing__")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])
    boolean = Pipeline([("imputer", SimpleImputer(strategy="most_frequent"))])
    preprocessor = ColumnTransformer([
        ("numeric", numeric, list(CONTRACT.numeric)),
        ("categorical", categorical, list(CONTRACT.categorical)),
        ("boolean", boolean, list(CONTRACT.boolean)),
    ])
    return Pipeline([
        ("preprocessor", preprocessor),
        ("model", LogisticRegression(max_iter=1000, class_weight=None)),
    ])


def target_from_outcome(values: pd.Series) -> pd.Series:
    unexpected = sorted(set(values.dropna()) - {"cerrado", "perdido"})
    if unexpected:
        raise ValueError(f"Unexpected outcomes: {unexpected}")
    return values.map({"cerrado": 1, "perdido": 0}).astype(int)


def temporal_split(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp]:
    ordered = frame.copy()
    ordered["fecha_registro"] = pd.to_datetime(ordered["fecha_registro"])
    ordered = ordered.sort_values(["fecha_registro", "raw_row_id"]).reset_index(drop=True)
    cutoff_index = max(1, int(len(ordered) * 0.8)) - 1
    cutoff = pd.Timestamp(ordered.loc[cutoff_index, "fecha_registro"])
    train = ordered[ordered.fecha_registro <= cutoff].copy()
    test = ordered[ordered.fecha_registro > cutoff].copy()
    if test.empty:
        raise ValueError("Temporal split produced an empty test set")
    return train, test, cutoff


def dataset_hash(frame: pd.DataFrame) -> str:
    columns = ["raw_row_id", "fecha_registro", *CONTRACT.columns, "desenlace_normalizado"]
    records = frame.loc[:, columns].sort_values("raw_row_id").to_dict(orient="records")
    payload = json.dumps(
        records, default=str, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def coefficient_rows(pipeline: Pipeline) -> list[dict[str, Any]]:
    preprocessor = pipeline.named_steps["preprocessor"]
    model = pipeline.named_steps["model"]
    names = preprocessor.get_feature_names_out()
    coefficients = model.coef_[0]
    rows = []
    for name, coefficient in zip(names, coefficients, strict=True):
        rows.append({
            "feature": name,
            "coefficient": float(coefficient),
            "abs_coefficient": abs(float(coefficient)),
            "direction": "positive" if coefficient >= 0 else "negative",
        })
    return sorted(rows, key=lambda row: row["abs_coefficient"], reverse=True)


def run(output_dir: Path, database_url: str | None = None) -> dict[str, Any]:
    db_url = database_url or settings.database_url
    if not db_url:
        raise RuntimeError("DATABASE_URL is required")
    output_dir.mkdir(parents=True, exist_ok=True)
    with connect(db_url) as connection:
        historical = pd.DataFrame(fetch_rows(connection, training_query()))
        serving = pd.DataFrame(fetch_rows(connection, serving_query()))
        capacity_share = fetch_capacity_share(connection, len(serving))
    target = target_from_outcome(historical["desenlace_normalizado"])
    historical["target"] = target
    historical["fecha_registro"] = pd.to_datetime(historical["fecha_registro"])
    if historical["fecha_registro"].isna().any():
        raise ValueError("fecha_registro cannot be null for temporal validation")
    train, test, cutoff = temporal_split(historical)
    pipeline = build_pipeline()
    pipeline.fit(prepare_features(train), train.target)
    test_scores = pipeline.predict_proba(prepare_features(test))[:, 1]
    y_test = test.target.to_numpy()
    fifo_order = np.argsort(test.fecha_registro.to_numpy(), kind="stable")
    metrics = evaluate_predictions(y_test, test_scores)
    for label, fraction in (("10pct", 0.10), ("20pct", 0.20)):
        k = max(1, int(np.ceil(len(test) * fraction)))
        metrics[label] = ranking_metrics(y_test, test_scores, fifo_order, k)
    if capacity_share is not None:
        metrics["capacity_share"] = ranking_metrics(
            y_test, test_scores, fifo_order, max(1, int(np.ceil(len(test) * capacity_share)))
        )
    training_hash = dataset_hash(historical)
    joblib.dump(pipeline, output_dir / "propensity_model.joblib")
    coefficients = coefficient_rows(pipeline)
    pd.DataFrame(coefficients).to_csv(output_dir / "propensity_coefficients.csv", index=False)
    scored_at = datetime.now(UTC)
    score_rows, scores = score_serving_frame(pipeline, serving, training_hash, scored_at)
    with connect(db_url) as connection:
        upsert_scores(connection, score_rows)
    metadata = {
        "model_type": "sklearn.linear_model.LogisticRegression",
        "model_version": MODEL_VERSION,
        "feature_columns": CONTRACT.columns,
        "numeric_features": list(CONTRACT.numeric),
        "categorical_features": list(CONTRACT.categorical),
        "boolean_features": list(CONTRACT.boolean),
        "excluded_features": EXCLUDED_FEATURES,
        "leakage_audit": [
            {"feature": f, "classification": c, "used": u, "reason": r}
            for f, c, u, r in LEAKAGE_AUDIT
        ],
        "target_mapping": {"cerrado": 1, "perdido": 0, "sin gestion": "excluded"},
        "training_rows": len(historical),
        "train_rows": len(train),
        "test_rows": len(test),
        "train_date_min": str(train.fecha_registro.min()),
        "train_date_max": str(train.fecha_registro.max()),
        "test_date_min": str(test.fecha_registro.min()),
        "test_date_max": str(test.fecha_registro.max()),
        "cutoff": str(cutoff.date()),
        "train_positive_rate": float(train.target.mean()),
        "test_positive_rate": float(test.target.mean()),
        "capacity_share": capacity_share,
        "training_data_hash": training_hash,
        "metrics": metrics,
        "created_at": datetime.now(UTC).isoformat(),
    }
    (output_dir / "propensity_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (output_dir.parent.parent / "reports" / "ml").mkdir(parents=True, exist_ok=True)
    report_dir = output_dir.parent.parent / "reports" / "ml"
    (report_dir / "propensity_metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    pd.DataFrame(coefficients).to_csv(report_dir / "propensity_coefficients.csv", index=False)
    pd.DataFrame(
        LEAKAGE_AUDIT, columns=["feature", "classification", "used", "reason"]
    ).to_csv(report_dir / "propensity_leakage_audit.csv", index=False)
    return {"metadata": metadata, "coefficients": coefficients, "scores": scores}


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and score the lead propensity baseline")
    parser.add_argument("--database-url")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/ml"))
    args = parser.parse_args()
    result = run(args.output_dir, args.database_url)
    metadata = result["metadata"]
    print(json.dumps({
        "training_rows": metadata["training_rows"],
        "metrics": metadata["metrics"],
        "scored_rows": len(result["scores"]),
    }, indent=2))


if __name__ == "__main__":
    main()
