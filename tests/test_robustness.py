"""Robustness capstone: the pure functions behind the four hostile-reviewer
tests (``benchmark/robustness.py`` and the SHAP funnel split in
``explain/shap_baseline.py``).

These cover wiring and the load-bearing guarantees — the placebo collapses on a
separable toy, the sweep and controls count correctly, the funnel groups
partition the features exactly — not model quality. XGBoost fits are kept tiny.
"""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from hazium.benchmark.robustness import (
    cutoff_sweep,
    label_shuffle_placebo,
    negative_controls,
)
from hazium.explain.shap_baseline import FUNNEL_GROUPS, grouped_importance
from hazium.ml.baseline import CutoffResult
from hazium.ml.dataset import FEATURE_COLUMNS
from hazium.graph.store import TemporalGraph
from hazium.models import Node, NodeType, RegulatoryEvent, RegulatoryEventKind

CUTOFF = date(2023, 1, 1)


def _separable_dataset(n: int, n_pos: int) -> tuple[pd.DataFrame, pd.Series]:
    """A dataset where one feature *is* the label — real signal, cleanly
    separable, so the placebo has something real to collapse away from."""
    rng = np.random.default_rng(0)
    X = pd.DataFrame(
        rng.random((n, len(FEATURE_COLUMNS))) * 0.01,
        columns=FEATURE_COLUMNS,
        index=[f"s{i}" for i in range(n)],
    )
    y = pd.Series([1] * n_pos + [0] * (n - n_pos), index=X.index, name="label")
    # Make the first feature carry the label exactly.
    X[FEATURE_COLUMNS[0]] = y.to_numpy(dtype=float)
    return X, y


class TestLabelShufflePlacebo:
    def test_real_signal_towers_over_shuffled_null(self) -> None:
        X, y = _separable_dataset(40, 10)
        res = label_shuffle_placebo(X, y, "headline", CUTOFF, seed=0, n_permutations=5, repeats=1)
        # A perfectly separable feature must score far above every shuffled draw.
        assert res.real_ap > res.shuffled_max
        assert res.real_ap > 0.5
        # The null keeps the class balance, so its mean sits near the base rate.
        assert res.shuffled_mean < 5 * res.base_rate + 0.05

    def test_reports_class_balance_and_permutation_count(self) -> None:
        X, y = _separable_dataset(40, 10)
        res = label_shuffle_placebo(X, y, "headline", CUTOFF, seed=0, n_permutations=5, repeats=1)
        assert res.positives == 10
        assert res.population == 40
        assert res.base_rate == pytest.approx(0.25)
        assert res.n_permutations == 5

    def test_p_value_is_at_its_floor_when_real_beats_all(self) -> None:
        X, y = _separable_dataset(40, 10)
        res = label_shuffle_placebo(X, y, "headline", CUTOFF, seed=0, n_permutations=5, repeats=1)
        # No shuffled draw reaches the real AP -> smallest reportable p-value.
        assert res.p_value == pytest.approx(1 / 6)

    def test_deterministic_given_seed(self) -> None:
        X, y = _separable_dataset(40, 10)
        a = label_shuffle_placebo(X, y, "h", CUTOFF, seed=0, n_permutations=4, repeats=1)
        b = label_shuffle_placebo(X, y, "h", CUTOFF, seed=0, n_permutations=4, repeats=1)
        assert a.real_ap == b.real_ap
        assert a.shuffled_mean == b.shuffled_mean


def _cutoff_result(ids: list[str], y_true: list[int], scores: list[float]) -> CutoffResult:
    """Hand-build a scored cutoff — no model, so control/rank logic is testable
    against a known ranking."""
    return CutoffResult(
        cutoff=CUTOFF,
        ids=ids,
        y_true=np.array(y_true),
        scores={"xgboost": np.array(scores, dtype=float)},
        out_of_fold=True,
    )


class TestNegativeControls:
    def test_counts_controls_in_top_k_and_median(self) -> None:
        # 6 substances, scores descending by id order (s0 highest).
        ids = [f"s{i}" for i in range(6)]
        result = _cutoff_result(ids, [1, 0, 0, 0, 0, 0], [0.9, 0.8, 0.7, 0.6, 0.5, 0.4])
        # Controls s1 (rank 2) and s4 (rank 5).
        out = negative_controls(result, {"ctrl": {"s1", "s4"}}, "headline", k_values=(1, 3))
        (row,) = out
        assert row.n_present == 2
        assert row.in_top_k[1] == 0  # neither is rank 1
        assert row.in_top_k[3] == 1  # only s1 (rank 2) is within top-3
        assert row.median_rank == pytest.approx(3.5)  # median of ranks {2, 5}

    def test_absent_controls_are_ignored_not_zero(self) -> None:
        ids = ["s0", "s1"]
        result = _cutoff_result(ids, [1, 0], [0.9, 0.1])
        out = negative_controls(result, {"ctrl": {"s1", "not_in_population"}}, "h", k_values=(1,))
        (row,) = out
        assert row.n_present == 1  # the missing id contributes nothing

    def test_empty_group_reports_none_median(self) -> None:
        result = _cutoff_result(["s0"], [1], [0.9])
        out = negative_controls(result, {"ctrl": set()}, "h", k_values=(1,))
        (row,) = out
        assert row.n_present == 0
        assert row.median_rank is None
        assert row.median_percentile is None


class TestGroupedImportance:
    class _FakeExplanation:
        def __init__(self, mean_abs: dict[str, float]) -> None:
            # global_importance takes the column-wise mean of |values|; a single
            # row equal to the desired magnitudes reproduces those means exactly.
            self.feature_names = list(mean_abs)
            self.values = np.array([[mean_abs[c] for c in self.feature_names]])

    def test_shares_sum_to_one_and_match_group_sums(self) -> None:
        mags = {c: 0.0 for cols in FUNNEL_GROUPS.values() for c in cols}
        mags["lit_hazard_percentile"] = 3.0
        mags["efsa_n_assessments"] = 1.0
        rows = grouped_importance(self._FakeExplanation(mags))
        shares = {r["group"]: r["share"] for r in rows}
        assert sum(shares.values()) == pytest.approx(1.0)
        assert shares["outside_funnel"] == pytest.approx(0.75)
        assert shares["inside_funnel"] == pytest.approx(0.25)

    def test_raises_when_a_feature_is_unassigned(self) -> None:
        exp = self._FakeExplanation({"lit_hazard_percentile": 1.0, "surprise_feature": 1.0})
        with pytest.raises(ValueError, match="do not partition"):
            grouped_importance(exp)

    def test_raises_on_group_with_unknown_feature(self) -> None:
        exp = self._FakeExplanation({"lit_hazard_percentile": 1.0})
        with pytest.raises(ValueError, match="do not partition"):
            grouped_importance(exp, groups={"g": ("lit_hazard_percentile", "ghost_feature")})

    def test_default_groups_cover_every_model_feature(self) -> None:
        grouped = [c for cols in FUNNEL_GROUPS.values() for c in cols]
        assert sorted(grouped) == sorted(FEATURE_COLUMNS)
        assert len(grouped) == len(set(grouped))  # no feature in two groups


class TestCutoffSweep:
    def _graph(self) -> TemporalGraph:
        g = TemporalGraph()
        for cas, known in (("79622-59-6", date(2015, 1, 1)), ("11111-11-1", date(2010, 1, 1))):
            g.add_node(
                Node(
                    id=f"substance:cas:{cas}",
                    type=NodeType.SUBSTANCE,
                    label=cas,
                    source="s",
                    known_at=known,
                )
            )
        return g

    def _events(self) -> list[RegulatoryEvent]:
        return [
            RegulatoryEvent(
                substance_id="substance:cas:11111-11-1",
                kind=RegulatoryEventKind.NON_RENEWAL,
                jurisdiction="EU",
                event_date=date(2024, 6, 1),
                source="s",
                known_at=date(2024, 6, 1),
            )
        ]

    def test_returns_one_aggregate_row_per_cutoff(self) -> None:
        cutoffs = [date(2022, 1, 1), date(2023, 1, 1)]
        targets = [("Fluazinam", "79622-59-6")]
        res = cutoff_sweep(self._graph(), [], self._events(), cutoffs, targets, "headline")
        assert len(res.aggregate) == 2
        assert {r.cutoff for r in res.aggregate} == set(cutoffs)

    def test_returns_one_rank_row_per_cutoff_per_target(self) -> None:
        cutoffs = [date(2022, 1, 1), date(2023, 1, 1)]
        targets = [("Fluazinam", "79622-59-6"), ("Other", "11111-11-1")]
        res = cutoff_sweep(self._graph(), [], self._events(), cutoffs, targets, "headline")
        assert len(res.ranks) == 4
        fluazinam_rows = [r for r in res.ranks if r.name == "Fluazinam"]
        assert all(r.rank is not None for r in fluazinam_rows)  # always in population

    def test_positive_flag_tracks_future_action(self) -> None:
        # "Other" is non-renewed 2024-06 -> a future positive at a 2023 cutoff,
        # and censored out of the population once the action is realized.
        res = cutoff_sweep(
            self._graph(),
            [],
            self._events(),
            [date(2023, 1, 1)],
            [("Other", "11111-11-1")],
            "headline",
        )
        (row,) = res.ranks
        assert row.is_positive is True
