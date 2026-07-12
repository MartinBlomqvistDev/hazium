"""XGBoost baseline and trivial rankers, evaluated per rolling-origin cutoff.

Per the manifesto's baseline rule: every learned model is compared against a
tabular baseline, which is itself compared against dead-simple trivial
rankers on the same task and split. If XGBoost does not beat them, they are
the published result.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold
from xgboost import XGBClassifier

from hazium.graph.store import TemporalGraph
from hazium.ml.dataset import DEFAULT_POSITIVE_KINDS, build_dataset
from hazium.models import RegulatoryEvent, RegulatoryEventKind, SalesRecord

TRIVIAL_BASELINES = {
    "severe_hazard_count": lambda X: (
        X["clp_has_cmr"] + X["clp_has_aquatic_chronic_1"] + X["clp_has_stot"]
    ),
    "latest_sales_tonnage": lambda X: X["sales_latest_tonnage"],
    "efsa_assessment_count": lambda X: X["efsa_n_assessments"],
}

K_VALUES = (10, 20, 50)


@dataclass(frozen=True)
class CutoffResult:
    """Everything one rolling-origin cutoff produced, ready to score."""

    cutoff: date
    ids: list[str]
    y_true: np.ndarray
    scores: dict[str, np.ndarray]  # model name -> score array, same row order as ids
    out_of_fold: bool  # False only in the degenerate <2-positives fallback

    @property
    def population(self) -> int:
        return len(self.ids)

    @property
    def positives(self) -> int:
        return int(self.y_true.sum())


def make_model(y: pd.Series, seed: int = 42) -> XGBClassifier:
    n_pos = max(int(y.sum()), 1)
    n_neg = len(y) - n_pos
    return XGBClassifier(
        n_estimators=200,
        max_depth=3,
        learning_rate=0.1,
        scale_pos_weight=n_neg / n_pos,
        eval_metric="aucpr",
        random_state=seed,
    )


def score_xgboost(X: pd.DataFrame, y: pd.Series, seed: int = 42) -> tuple[np.ndarray, bool]:
    """Predicted probabilities, out-of-fold via stratified k-fold CV.

    Out-of-fold, not in-sample: fitting on the full (X, y) and scoring those
    same rows would be optimistic — the model has seen the label it's being
    graded on. Folds are capped so each still holds >=2 positives; below that
    (fewer than 2 positives total) CV can't stratify meaningfully, and this
    falls back to in-sample fit-and-predict, flagged via the returned bool so
    callers can report the result as descriptive rather than held-out.
    """
    n_pos = int(y.sum())
    if n_pos < 2:
        model = make_model(y, seed)
        model.fit(X, y)
        return model.predict_proba(X)[:, 1], False

    n_splits = max(2, min(5, n_pos))
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    scores = np.zeros(len(y))
    for train_idx, test_idx in skf.split(X, y):
        model = make_model(y.iloc[train_idx], seed)
        model.fit(X.iloc[train_idx], y.iloc[train_idx])
        scores[test_idx] = model.predict_proba(X.iloc[test_idx])[:, 1]
    return scores, True


def evaluate_cutoff(
    graph: TemporalGraph,
    sales: list[SalesRecord],
    regevents: list[RegulatoryEvent],
    cutoff: date,
    seed: int = 42,
    positive_kinds: frozenset[RegulatoryEventKind] = DEFAULT_POSITIVE_KINDS,
) -> CutoffResult:
    X, y, ids = build_dataset(graph, sales, regevents, cutoff, positive_kinds)
    xgb_scores, out_of_fold = score_xgboost(X, y, seed)

    scores = {name: fn(X).to_numpy(dtype=float) for name, fn in TRIVIAL_BASELINES.items()}
    scores["xgboost"] = xgb_scores

    return CutoffResult(
        cutoff=cutoff,
        ids=ids,
        y_true=y.to_numpy(),
        scores=scores,
        out_of_fold=out_of_fold,
    )


def rolling_origin_eval(
    graph: TemporalGraph,
    sales: list[SalesRecord],
    regevents: list[RegulatoryEvent],
    cutoffs: list[date],
    seed: int = 42,
    positive_kinds: frozenset[RegulatoryEventKind] = DEFAULT_POSITIVE_KINDS,
) -> list[CutoffResult]:
    return [
        evaluate_cutoff(graph, sales, regevents, cutoff, seed, positive_kinds) for cutoff in cutoffs
    ]
