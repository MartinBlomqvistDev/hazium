"""Robustness capstone: the three hostile-reviewer tests that harden every
HEWB headline number before the benchmark is broadcast publicly.

Per ``STRATEGY_SCOPE.md`` Move 1. The result table already shows a strong
lead over trivial baselines; the job here is not another number, it is making
the *existing* numbers survive a skeptical domain reader who asks the three
obvious questions:

* **Is the signal real, or did XGBoost overfit a small positive class?**
  → ``label_shuffle_placebo``. Refit on permuted labels; average precision must
  collapse toward the base rate. This is the genuine project kill-criterion
  (``MANIFESTO.md`` §10): if a shuffled label scores like the real one, the
  headline is an artifact and must be retracted, not caveated.

* **Is 2023 a cherry-picked cutoff?** → ``cutoff_sweep``. Report each
  landmark's rank at several annual cutoffs; a stable rank across 2022/2023/2024
  shows the result is not a single-cutoff accident. Mostly reporting — it reuses
  ``evaluate_cutoff``/``rank_of`` unchanged.

* **Does the model just flag anything hazardous?** → ``negative_controls``. A
  specificity test a ranking metric alone hides: substances that went through EU
  review and stayed approved (and the hazard-matched subset of them) should
  *not* concentrate at the top of the ranking.

Everything here is pure over its inputs (a graph, sales, regulatory events, an
already-built ``CutoffResult``). ``pipeline/20_run_robustness.py`` is the I/O
boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import median

import numpy as np
import pandas as pd

from hazium.benchmark.hewb import rank_of
from hazium.graph.store import TemporalGraph
from hazium.ml.baseline import CutoffResult, evaluate_cutoff, score_xgboost
from hazium.ml.dataset import DEFAULT_POSITIVE_KINDS
from hazium.ml.evaluate import average_precision
from hazium.models import (
    CLHIntentionRecord,
    LiteratureVolumeRecord,
    RegulatoryEvent,
    RegulatoryEventKind,
    SalesRecord,
)

#: The placebo scores real and permuted labels identically at this many CV
#: repeats. Lower than HEWB's ``N_SCORING_REPEATS`` (10) on purpose: the
#: permutation test needs dozens of full refits, and the null-vs-real
#: separation is enormous (real AP is ~15x the base rate) — fold-assignment
#: variance, the reason HEWB averages 10 repeats, is irrelevant to a test whose
#: whole point is a gross collapse, not a rank near a k threshold. Applied to
#: both the real and the shuffled fits so the comparison stays fair.
PLACEBO_REPEATS = 3

#: How many label permutations form the null distribution. 50 gives a smallest
#: reportable permutation p-value of 1/51 ≈ 0.02, enough to state "the real AP
#: is above the entire null" with a real number attached rather than a hand-wave.
PLACEBO_PERMUTATIONS = 50


@dataclass(frozen=True)
class PlaceboResult:
    """Outcome of one label-shuffle placebo at one cutoff / label variant.

    ``p_value`` is the permutation p-value ``(1 + #{shuffled >= real}) /
    (n_permutations + 1)``. A collapse (``real_ap`` far above ``shuffled_max``,
    ``shuffled_mean`` near ``base_rate``) is the pass condition; a shuffled AP
    reaching the real one is the documented kill signal.
    """

    variant: str
    cutoff: date
    population: int
    positives: int
    base_rate: float
    real_ap: float
    shuffled_mean: float
    shuffled_max: float
    shuffled_p95: float
    p_value: float
    n_permutations: int
    repeats: int


def label_shuffle_placebo(
    X,
    y,
    variant: str,
    cutoff: date,
    seed: int = 42,
    n_permutations: int = PLACEBO_PERMUTATIONS,
    repeats: int = PLACEBO_REPEATS,
) -> PlaceboResult:
    """Permutation test: refit on shuffled labels; AP must collapse to baseline.

    The null keeps the exact class balance (it permutes the label vector, so the
    positive count is unchanged) and breaks only the link between features and
    label. If XGBoost still scores well under that null, it was fitting noise in
    a small positive class, and the real result is an artifact.

    ``X``/``y`` are one cutoff's design matrix and label from ``build_dataset``.
    Pure and deterministic given ``seed``: the permutations are drawn from a
    seeded generator and each permuted fit uses a distinct, derived scoring seed.
    """
    y_values = np.asarray(y)
    real_scores, _ = score_xgboost(X, y, seed=seed, repeats=repeats)
    real_ap = average_precision(y_values, real_scores)

    index = y.index if isinstance(y, pd.Series) else pd.RangeIndex(len(y_values))
    rng = np.random.default_rng(seed)
    shuffled: list[float] = []
    for i in range(n_permutations):
        permuted = rng.permutation(y_values)
        # score_xgboost stratifies via ``y.iloc`` — the permuted labels must be a
        # Series aligned to X, not a bare array.
        permuted_series = pd.Series(permuted, index=index, name="label")
        # A distinct scoring seed per permutation so the CV split is not shared
        # across permutations (which would correlate the null draws).
        scores, _ = score_xgboost(X, permuted_series, seed=seed + 1000 * (i + 1), repeats=repeats)
        shuffled.append(average_precision(permuted, scores))

    shuffled_arr = np.asarray(shuffled)
    n_ge = int((shuffled_arr >= real_ap).sum())
    return PlaceboResult(
        variant=variant,
        cutoff=cutoff,
        population=len(y_values),
        positives=int(y_values.sum()),
        base_rate=float(y_values.mean()),
        real_ap=real_ap,
        shuffled_mean=float(shuffled_arr.mean()),
        shuffled_max=float(shuffled_arr.max()),
        shuffled_p95=float(np.percentile(shuffled_arr, 95)),
        p_value=(1 + n_ge) / (n_permutations + 1),
        n_permutations=n_permutations,
        repeats=repeats,
    )


@dataclass(frozen=True)
class SweepAggregateRow:
    """The whole-ranking headline at one cutoff — the cherry-pick test proper.

    The "is 2023 special?" question is about the *aggregate* result, not any one
    substance: does XGBoost beat the trivial baselines at every recent cutoff, or
    only at 2023? ``xgboost_ap`` towering over ``best_trivial_ap`` at each cutoff
    is the pass condition.
    """

    variant: str
    cutoff: date
    population: int
    positives: int
    base_rate: float
    xgboost_ap: float
    best_trivial_ap: float


@dataclass(frozen=True)
class SweepRankRow:
    """One target substance's rank at one cutoff (the north-star trajectory).

    A ``None`` rank means the substance was not in the population at that cutoff
    (no pre-cutoff dated fact, or its label-defining action was already realized
    and censored out — as most landmark bans are at recent cutoffs).
    ``is_positive`` records whether the substance is a future-action positive
    under this variant at this cutoff, which is what makes its rank meaningful.
    """

    variant: str
    name: str
    cas: str
    cutoff: date
    rank: int | None
    population: int
    is_positive: bool


@dataclass(frozen=True)
class SweepResult:
    """The full cutoff-sweep: aggregate cherry-pick test + target trajectories."""

    aggregate: list[SweepAggregateRow]
    ranks: list[SweepRankRow]


def cutoff_sweep(
    graph: TemporalGraph,
    sales: list[SalesRecord],
    regevents: list[RegulatoryEvent],
    cutoffs: list[date],
    targets: list[tuple[str, str]],
    variant: str,
    positive_kinds: frozenset[RegulatoryEventKind] = DEFAULT_POSITIVE_KINDS,
    seed: int = 42,
    lit_records: list[LiteratureVolumeRecord] = (),
    clh_records: list[CLHIntentionRecord] = (),
) -> SweepResult:
    """Aggregate AP and target ranks at every cutoff, under one label variant.

    Two outputs from one pass over the cutoffs:

    * ``aggregate`` — XGBoost AP vs the best trivial baseline at each cutoff. This
      is the real answer to "is 2023 cherry-picked?": a stable lead across cutoffs
      shows the headline result is not a single-cutoff artifact.
    * ``ranks`` — each target's rank at each cutoff (``targets`` is a list of
      ``(name, cas)``; the id is ``substance:cas:{cas}``). This is the north-star
      trajectory (fluazinam) and any landmark still in-population; a landmark
      censored out post-action correctly reads ``None``.

    Reuses ``evaluate_cutoff``/``rank_of`` so every number matches HEWB's — a
    re-view of the existing machinery, not a second scoring path.
    """
    aggregate: list[SweepAggregateRow] = []
    ranks: list[SweepRankRow] = []
    for cutoff in cutoffs:
        result = evaluate_cutoff(
            graph,
            sales,
            regevents,
            cutoff,
            seed=seed,
            positive_kinds=positive_kinds,
            lit_records=lit_records,
            clh_records=clh_records,
        )
        trivial_aps = [
            average_precision(result.y_true, scores)
            for name, scores in result.scores.items()
            if name != "xgboost"
        ]
        aggregate.append(
            SweepAggregateRow(
                variant=variant,
                cutoff=cutoff,
                population=result.population,
                positives=result.positives,
                base_rate=float(result.y_true.mean()),
                xgboost_ap=average_precision(result.y_true, result.scores["xgboost"]),
                best_trivial_ap=max(trivial_aps) if trivial_aps else 0.0,
            )
        )
        pos_by_id = dict(zip(result.ids, result.y_true))
        for name, cas in targets:
            sid = f"substance:cas:{cas}"
            ranks.append(
                SweepRankRow(
                    variant=variant,
                    name=name,
                    cas=cas,
                    cutoff=cutoff,
                    rank=rank_of(result, sid),
                    population=result.population,
                    is_positive=bool(pos_by_id.get(sid, 0)),
                )
            )
    return SweepResult(aggregate=aggregate, ranks=ranks)


@dataclass(frozen=True)
class ControlGroupResult:
    """Specificity outcome for one named control group at one cutoff.

    ``in_top_k`` counts controls that land in the top-k of the ranking despite
    never being actioned; a specific model keeps that count low. ``median_rank``
    and ``median_percentile`` (rank / population, so higher = worse-ranked =
    more benign-looking) summarise where the group sits overall.
    """

    variant: str
    cutoff: date
    label: str
    n_present: int
    in_top_k: dict[int, int]
    median_rank: float | None
    median_percentile: float | None


def negative_controls(
    result: CutoffResult,
    control_groups: dict[str, set[str]],
    variant: str,
    k_values: tuple[int, ...] = (10, 20, 50),
) -> list[ControlGroupResult]:
    """Where reviewed-but-not-banned substances land in the ranking.

    ``control_groups`` maps a label ("approved_survivors",
    "hazardous_survivors") to a set of substance ids. For each group, among its
    members present in the population, count how many reach each top-k and report
    the median rank / percentile. The pass condition is a low top-k count and a
    median deep in the ranking: the model is not merely flagging "is an approved
    pesticide" or "carries a severe hazard flag".

    Pure over an already-built ``CutoffResult`` — no scoring happens here.
    """
    population = result.population
    out: list[ControlGroupResult] = []
    for label, ids in control_groups.items():
        ranks = [r for sid in ids if (r := rank_of(result, sid)) is not None]
        in_top_k = {k: sum(1 for r in ranks if r <= k) for k in k_values}
        out.append(
            ControlGroupResult(
                variant=variant,
                cutoff=result.cutoff,
                label=label,
                n_present=len(ranks),
                in_top_k=in_top_k,
                median_rank=median(ranks) if ranks else None,
                median_percentile=(median(ranks) / population) if ranks and population else None,
            )
        )
    return out
