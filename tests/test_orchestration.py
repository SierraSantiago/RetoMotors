import numpy as np
import pandas as pd

from reto_ia.ml.scoring import score_serving_frame
from reto_ia.orchestration import daily


class PredictOnlyPipeline:
    def predict_proba(self, frame):
        assert len(frame) == 1
        return np.array([[0.8, 0.2]])


def test_daily_scoring_uses_predict_proba_without_fit():
    serving = pd.DataFrame({
        "raw_row_id": ["r1"], "lead_id": ["l1"], "precio_lista": [1.0],
        "empresa_id": ["e1"], "punto_venta_id": ["p1"], "canal_normalizado": ["web"],
        "modelo_feature": ["m1"], "manifesto_cuota_inicial": [False], "pidio_cita": [False],
    })
    rows, scores = score_serving_frame(PredictOnlyPipeline(), serving, "hash")
    assert rows[0]["propensity_score"] == 0.2
    assert scores.tolist() == [0.2]


def test_daily_flow_is_sequential_and_does_not_train(monkeypatch):
    order = []
    monkeypatch.setattr(daily, "source_ingestion", lambda *_: order.append("ingestion"))
    monkeypatch.setattr(daily, "dbt_conversation_staging", lambda *_: order.append("staging"))
    monkeypatch.setattr(daily, "pending_conversation_extraction", lambda *_: order.append("llm"))
    monkeypatch.setattr(daily, "dbt_full_build", lambda *_: order.append("dbt"))
    monkeypatch.setattr(
        daily, "propensity_inference", lambda *_: order.append("score") or {"scored_rows": 0}
    )
    monkeypatch.setattr(daily, "daily_priority_assignment", lambda *_: order.append("priority"))
    monkeypatch.setattr(daily, "operational_validation", lambda *_: order.append("validate") or {})

    daily.run_daily_pipeline(assignment_date="2026-09-17")

    assert order == ["ingestion", "staging", "llm", "dbt", "score", "priority", "validate"]


def test_daily_flow_skip_ingestion_continues_with_remaining_tasks(monkeypatch):
    order = []
    monkeypatch.setattr(daily, "source_ingestion", lambda *_: order.append("ingestion"))
    monkeypatch.setattr(daily, "dbt_conversation_staging", lambda *_: order.append("staging"))
    monkeypatch.setattr(daily, "pending_conversation_extraction", lambda *_: order.append("llm"))
    monkeypatch.setattr(daily, "dbt_full_build", lambda *_: order.append("dbt"))
    monkeypatch.setattr(
        daily, "propensity_inference", lambda *_: order.append("score") or {"scored_rows": 0}
    )
    monkeypatch.setattr(daily, "daily_priority_assignment", lambda *_: order.append("priority"))
    monkeypatch.setattr(daily, "operational_validation", lambda *_: order.append("validate") or {})

    daily.run_daily_pipeline(assignment_date="2026-09-17", skip_ingestion=True)

    assert order == ["staging", "llm", "dbt", "score", "priority", "validate"]
