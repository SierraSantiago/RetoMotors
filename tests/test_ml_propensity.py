import numpy as np
import pandas as pd
import pytest

from reto_ia.ml.features import CONTRACT, EXCLUDED_FEATURES, prepare_features
from reto_ia.ml.training import build_pipeline, target_from_outcome, temporal_split


def frame(rows: int = 10) -> pd.DataFrame:
    return pd.DataFrame({
        "raw_row_id": [f"r{i}" for i in range(rows)],
        "fecha_registro": pd.date_range("2026-01-01", periods=rows),
        "empresa_id": ["e1"] * rows,
        "punto_venta_id": ["p1"] * rows,
        "canal_normalizado": ["web"] * rows,
        "modelo_feature": ["m1"] * rows,
        "precio_lista": [10_000_000.0] * rows,
        "manifesto_cuota_inicial": [True, False] * (rows // 2),
        "pidio_cita": [False] * rows,
        "desenlace_normalizado": ["cerrado", "perdido"] * (rows // 2),
    })


def test_target_mapping_excludes_unmanaged_and_rejects_unexpected():
    assert target_from_outcome(pd.Series(["cerrado", "perdido"])).tolist() == [1, 0]
    with pytest.raises(ValueError, match="Unexpected outcomes"):
        target_from_outcome(pd.Series(["cerrado", "sin gestion"]))


def test_temporal_split_has_no_random_leakage():
    train, test, _ = temporal_split(frame())
    assert train.fecha_registro.max() < test.fecha_registro.min()


def test_contract_excludes_post_treatment_and_supports_unknown_categories():
    assert "numero_contactos" in EXCLUDED_FEATURES
    assert "horas_al_primer_contacto" in EXCLUDED_FEATURES
    pipeline = build_pipeline()
    data = frame()
    pipeline.fit(prepare_features(data), np.array([0, 1] * 5))
    serving = data.iloc[:1].copy()
    serving["canal_normalizado"] = "new-channel"
    predictions = pipeline.predict_proba(prepare_features(serving))
    assert predictions.shape == (1, 2)
    assert 0 <= predictions[0, 1] <= 1


def test_contract_columns_are_shared_by_train_and_serving():
    assert set(CONTRACT.columns) == set(
        ["precio_lista", "empresa_id", "punto_venta_id", "canal_normalizado",
         "modelo_feature", "manifesto_cuota_inicial", "pidio_cita"]
    )
