from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


def ranking_metrics(
    y_true: np.ndarray, scores: np.ndarray, fifo_order: np.ndarray, k: int
) -> dict[str, float | int]:
    def metrics(order: np.ndarray) -> tuple[float, float, float]:
        selected = y_true[order[:k]]
        precision = float(selected.mean()) if len(selected) else 0.0
        recall = float(selected.sum() / y_true.sum()) if y_true.sum() else 0.0
        return precision, recall, precision

    model_p, model_r, _ = metrics(np.argsort(-scores, kind="stable"))
    fifo_p, fifo_r, _ = metrics(fifo_order)
    base_rate = float(y_true.mean())
    return {
        "k": k,
        "rows": min(k, len(y_true)),
        "model_precision": model_p,
        "fifo_precision": fifo_p,
        "model_recall": model_r,
        "fifo_recall": fifo_r,
        "model_lift": model_p / base_rate if base_rate else None,
        "fifo_lift": fifo_p / base_rate if base_rate else None,
    }


def evaluate_predictions(y_true: np.ndarray, scores: np.ndarray) -> dict[str, Any]:
    result: dict[str, Any] = {
        "roc_auc": float(roc_auc_score(y_true, scores)) if len(np.unique(y_true)) == 2 else None,
        "pr_auc": float(average_precision_score(y_true, scores)) if len(y_true) else None,
        "brier_score": float(brier_score_loss(y_true, scores)) if len(y_true) else None,
        "test_positive_rate": float(y_true.mean()) if len(y_true) else None,
    }
    return result
