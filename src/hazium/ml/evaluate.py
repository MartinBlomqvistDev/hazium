"""Imbalanced-ranking metrics. Never accuracy or ROC-AUC — with a 1-4% base
rate, both are dominated by the negative class and hide exactly the signal
this project cares about (see ``V1_SCOPE.md``'s evaluation protocol).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from sklearn.metrics import average_precision_score

if TYPE_CHECKING:
    from hazium.ml.baseline import CutoffResult

K_VALUES = (10, 20, 50)


def average_precision(y_true: np.ndarray, scores: np.ndarray) -> float:
    """PR-AUC. 0.0 (not undefined) when there are no positives to rank."""
    if y_true.sum() == 0:
        return 0.0
    return float(average_precision_score(y_true, scores))


def _top_k_indices(scores: np.ndarray, k: int) -> np.ndarray:
    k = min(k, len(scores))
    return np.argsort(-scores, kind="stable")[:k]


def precision_at_k(y_true: np.ndarray, scores: np.ndarray, k: int) -> float:
    if k <= 0 or len(scores) == 0:
        return 0.0
    top = _top_k_indices(scores, k)
    return float(y_true[top].sum() / len(top))


def recall_at_k(y_true: np.ndarray, scores: np.ndarray, k: int) -> float:
    total_positives = y_true.sum()
    if total_positives == 0 or k <= 0 or len(scores) == 0:
        return 0.0
    top = _top_k_indices(scores, k)
    return float(y_true[top].sum() / total_positives)


def lift_at_k(y_true: np.ndarray, scores: np.ndarray, k: int) -> float:
    """Precision@k divided by the population base rate. 0.0 if no positives."""
    base_rate = y_true.mean() if len(y_true) else 0.0
    if base_rate == 0:
        return 0.0
    return precision_at_k(y_true, scores, k) / base_rate


def bootstrap_ci(
    y_true: np.ndarray,
    scores: np.ndarray,
    metric_fn,
    n_boot: int = 200,
    seed: int = 42,
    ci: float = 0.90,
) -> tuple[float, float]:
    """Percentile bootstrap CI for a metric, resampling rows with replacement.

    ``metric_fn`` takes ``(y_true, scores)`` (e.g. ``average_precision``, or a
    ``functools.partial`` binding ``k`` for the ``@k`` metrics). With a small
    positive class, resamples can draw zero positives; ``metric_fn`` must
    handle that (all the metrics above return 0.0 rather than raising).
    """
    rng = np.random.default_rng(seed)
    n = len(y_true)
    if n == 0:
        return (0.0, 0.0)
    values = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        values[i] = metric_fn(y_true[idx], scores[idx])
    lo = (1 - ci) / 2 * 100
    hi = (1 - (1 - ci) / 2) * 100
    return (float(np.percentile(values, lo)), float(np.percentile(values, hi)))


def summarize(result: "CutoffResult") -> list[dict]:
    """One row per model for a cutoff: AP (with bootstrap CI) + P@k/R@k/lift@k.

    This is the published eval table's raw material (``V1_SCOPE.md``'s
    "Deliverable / V1 gate"): a plain list of dicts, trivial to print, write
    to CSV/JSON, or filter down to a pesticide-only subset by row id before
    calling this (subsetting happens at the caller, on ``result.ids``).
    """
    rows = []
    for model_name, scores in result.scores.items():
        ap = average_precision(result.y_true, scores)
        ap_lo, ap_hi = bootstrap_ci(result.y_true, scores, average_precision)
        row = {
            "cutoff": result.cutoff.isoformat(),
            "model": model_name,
            "population": result.population,
            "positives": result.positives,
            "average_precision": ap,
            "ap_ci_lo": ap_lo,
            "ap_ci_hi": ap_hi,
        }
        for k in K_VALUES:
            row[f"precision_at_{k}"] = precision_at_k(result.y_true, scores, k)
            row[f"recall_at_{k}"] = recall_at_k(result.y_true, scores, k)
            row[f"lift_at_{k}"] = lift_at_k(result.y_true, scores, k)
        rows.append(row)
    return rows
