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
from hazium.ml.embed import embedding_dataframe, fit_metapath2vec
from hazium.models import (
    CLHIntentionRecord,
    LiteratureVolumeRecord,
    RegulatoryEvent,
    RegulatoryEventKind,
    SalesRecord,
)

TRIVIAL_BASELINES = {
    "severe_hazard_count": lambda X: (
        X["clp_has_cmr"] + X["clp_has_aquatic_chronic_1"] + X["clp_has_stot"]
    ),
    "latest_sales_tonnage": lambda X: X["sales_latest_tonnage"],
    "efsa_assessment_count": lambda X: X["efsa_n_assessments"],
}

K_VALUES = (10, 20, 50)

#: Out-of-fold scores are averaged over this many independent CV shuffles.
#: A single ``StratifiedKFold(shuffle=True)`` split assigns every substance to
#: one fold; with a small positive class (tens of positives in a ~5,900-row
#: population) the fold a borderline substance lands in materially moves its
#: out-of-fold score, so the exact rank near a k threshold is partly an
#: artifact of one random fold assignment. Verified 2026-07-19 (DEV_LOG, HEWB
#: v1.3): a single-substance data change (the Maneb/Mancozeb split) swung
#: Thiamethoxam's 2009 rank from 9 to 47 under single-shuffle scoring, while
#: substances ranked deep inside the top-k were unmoved. Averaging the
#: out-of-fold probability over several shuffles removes the fold-assignment
#: variance and makes lead-times reproducible; 10 is the standard
#: repeated-CV default, enough to stabilise the ranking without turning the
#: benchmark into a compute sink.
N_SCORING_REPEATS = 10


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
    """Predicted probabilities, out-of-fold via *repeated* stratified k-fold CV.

    Out-of-fold, not in-sample: fitting on the full (X, y) and scoring those
    same rows would be optimistic — the model has seen the label it's being
    graded on. Folds are capped so each still holds >=2 positives; below that
    (fewer than 2 positives total) CV can't stratify meaningfully, and this
    falls back to in-sample fit-and-predict, flagged via the returned bool so
    callers can report the result as descriptive rather than held-out.

    The out-of-fold probability is averaged over ``N_SCORING_REPEATS``
    independent shuffles (seeds ``seed .. seed + N_SCORING_REPEATS - 1``), each
    a full out-of-fold pass. This removes the fold-assignment variance that a
    single shuffle leaves in a small-positive-class ranking problem — see
    ``N_SCORING_REPEATS`` for the finding that motivated it. Deterministic
    given ``seed``: reproducible, just no longer hostage to one random split.
    """
    n_pos = int(y.sum())
    if n_pos < 2:
        model = make_model(y, seed)
        model.fit(X, y)
        return model.predict_proba(X)[:, 1], False

    n_splits = max(2, min(5, n_pos))
    accumulated = np.zeros(len(y))
    for repeat in range(N_SCORING_REPEATS):
        repeat_seed = seed + repeat
        skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=repeat_seed)
        for train_idx, test_idx in skf.split(X, y):
            model = make_model(y.iloc[train_idx], repeat_seed)
            model.fit(X.iloc[train_idx], y.iloc[train_idx])
            accumulated[test_idx] += model.predict_proba(X.iloc[test_idx])[:, 1]
    return accumulated / N_SCORING_REPEATS, True


def evaluate_cutoff(
    graph: TemporalGraph,
    sales: list[SalesRecord],
    regevents: list[RegulatoryEvent],
    cutoff: date,
    seed: int = 42,
    positive_kinds: frozenset[RegulatoryEventKind] = DEFAULT_POSITIVE_KINDS,
    lit_records: list[LiteratureVolumeRecord] = (),
    clh_records: list[CLHIntentionRecord] = (),
) -> CutoffResult:
    X, y, ids = build_dataset(
        graph, sales, regevents, cutoff, positive_kinds, lit_records, clh_records
    )
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
    lit_records: list[LiteratureVolumeRecord] = (),
    clh_records: list[CLHIntentionRecord] = (),
) -> list[CutoffResult]:
    return [
        evaluate_cutoff(
            graph, sales, regevents, cutoff, seed, positive_kinds, lit_records, clh_records
        )
        for cutoff in cutoffs
    ]


def evaluate_cutoff_with_embeddings(
    graph: TemporalGraph,
    sales: list[SalesRecord],
    regevents: list[RegulatoryEvent],
    cutoff: date,
    seed: int = 42,
    positive_kinds: frozenset[RegulatoryEventKind] = DEFAULT_POSITIVE_KINDS,
    embed_dim: int = 32,
    lit_records: list[LiteratureVolumeRecord] = (),
) -> CutoffResult:
    """V2b: the baseline rule, literally -- tabular alone, embedding alone,
    and tabular+embedding concatenated, on the identical population/split/seed.

    The embedding is fit fresh on ``graph.as_of(cutoff)`` inside this one
    call (see ``ml/embed.py``'s module docstring for why that is the entire
    leakage-safety story): there is no separate "fit once, reuse per cutoff"
    step available to get wrong, because calling this per-cutoff *is* the
    refit.
    """
    X, y, ids = build_dataset(graph, sales, regevents, cutoff, positive_kinds, lit_records)
    view = graph.as_of(cutoff)
    vectors = fit_metapath2vec(view, ids, dim=embed_dim, seed=seed)
    X_embed = embedding_dataframe(vectors, ids, embed_dim)
    X_concat = pd.concat([X, X_embed], axis=1)

    tabular_scores, tabular_oof = score_xgboost(X, y, seed)
    embed_scores, embed_oof = score_xgboost(X_embed, y, seed)
    concat_scores, concat_oof = score_xgboost(X_concat, y, seed)

    scores = {name: fn(X).to_numpy(dtype=float) for name, fn in TRIVIAL_BASELINES.items()}
    scores["xgboost_tabular"] = tabular_scores
    scores["xgboost_embed_only"] = embed_scores
    scores["xgboost_tabular_plus_embed"] = concat_scores

    return CutoffResult(
        cutoff=cutoff,
        ids=ids,
        y_true=y.to_numpy(),
        scores=scores,
        out_of_fold=tabular_oof and embed_oof and concat_oof,
    )


def rolling_origin_eval_with_embeddings(
    graph: TemporalGraph,
    sales: list[SalesRecord],
    regevents: list[RegulatoryEvent],
    cutoffs: list[date],
    seed: int = 42,
    positive_kinds: frozenset[RegulatoryEventKind] = DEFAULT_POSITIVE_KINDS,
    embed_dim: int = 32,
    lit_records: list[LiteratureVolumeRecord] = (),
) -> list[CutoffResult]:
    return [
        evaluate_cutoff_with_embeddings(
            graph, sales, regevents, cutoff, seed, positive_kinds, embed_dim, lit_records
        )
        for cutoff in cutoffs
    ]
