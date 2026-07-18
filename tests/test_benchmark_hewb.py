"""HEWB benchmark logic: pure functions over hand-built CutoffResults.

No XGBoost or graph build is needed to test the lead-time logic — it operates
over already-computed per-cutoff results, so tests construct those directly
(fast, deterministic). The underlying ``as_of`` temporal cleanliness that
feeds those results is covered by ``test_graph_*`` and ``test_ml_baseline``'s
refit-invariance test; here the temporal guarantee under test is the
*window rule* (HEWB never counts a flag at or after the action date).
"""

from datetime import date

import numpy as np

from hazium.benchmark.hewb import (
    LANDMARK_CASES,
    LandmarkCase,
    action_date_for,
    compute_case_result,
    rank_of,
    verify_landmark_cas,
)
from hazium.graph.store import TemporalGraph
from hazium.ml.baseline import CutoffResult
from hazium.ml.dataset import DEFAULT_POSITIVE_KINDS
from hazium.models import Node, NodeType, RegulatoryEvent, RegulatoryEventKind

SUB = "substance:cas:2921-88-2"


def _result(cutoff: date, ranked_ids: list[str], population: int | None = None) -> CutoffResult:
    """A CutoffResult whose xgboost scores rank ``ranked_ids`` best-first.

    Scores are assigned descending so position 0 in ``ranked_ids`` is rank 1.
    ``population`` pads the id list with filler so rank thresholds are tested
    against a realistic denominator; the target must appear in ``ranked_ids``
    to be "in population".
    """
    ids = list(ranked_ids)
    n = population if population is not None else len(ids)
    while len(ids) < n:
        ids.append(f"filler-{len(ids)}")
    scores = np.array([float(n - i) for i in range(len(ids))])
    return CutoffResult(
        cutoff=cutoff,
        ids=ids,
        y_true=np.zeros(len(ids), dtype=int),
        scores={"xgboost": scores},
        out_of_fold=True,
    )


def _non_renewal(event_date: date) -> RegulatoryEvent:
    return RegulatoryEvent(
        substance_id=SUB,
        kind=RegulatoryEventKind.NON_RENEWAL,
        jurisdiction="EU",
        event_date=event_date,
        source="s",
        known_at=event_date,
    )


class TestRankOf:
    def test_best_score_is_rank_one(self) -> None:
        r = _result(date(2020, 1, 1), ["a", "b", "c"])
        assert rank_of(r, "a") == 1
        assert rank_of(r, "b") == 2
        assert rank_of(r, "c") == 3

    def test_absent_substance_is_none_not_zero(self) -> None:
        r = _result(date(2020, 1, 1), ["a", "b"])
        assert rank_of(r, "missing") is None


class TestActionDateFor:
    def test_earliest_matching_action(self) -> None:
        events = [_non_renewal(date(2021, 1, 1)), _non_renewal(date(2017, 1, 1))]
        assert action_date_for(SUB, events, DEFAULT_POSITIVE_KINDS) == date(2017, 1, 1)

    def test_no_action_under_variant_is_none(self) -> None:
        # A reevaluation is not in DEFAULT_POSITIVE_KINDS (headline label).
        events = [
            RegulatoryEvent(
                substance_id=SUB,
                kind=RegulatoryEventKind.REEVALUATION_STARTED,
                jurisdiction="SE",
                event_date=date(2025, 1, 1),
                source="s",
                known_at=date(2025, 1, 1),
            )
        ]
        assert action_date_for(SUB, events, DEFAULT_POSITIVE_KINDS) is None


class TestComputeCaseResult:
    _CASE = LandmarkCase("Chlorpyrifos", "2921-88-2", "test")

    def _results(self) -> list[CutoffResult]:
        # rank trajectory: absent 2018, 100th 2019, 40th 2020, 8th 2021.
        return [
            _result(date(2018, 1, 1), ["x"], population=200),  # SUB absent
            _result(date(2019, 1, 1), ["filler"] * 99 + [SUB], population=200),  # rank 100
            _result(date(2020, 1, 1), ["filler"] * 39 + [SUB], population=200),  # rank 40
            _result(date(2021, 1, 1), ["filler"] * 7 + [SUB], population=200),  # rank 8
        ]

    def test_lead_time_at_each_k(self) -> None:
        events = [_non_renewal(date(2021, 7, 1))]
        cr = compute_case_result(
            self._CASE, "headline", self._results(), events, DEFAULT_POSITIVE_KINDS
        )
        assert cr.action_date == date(2021, 7, 1)
        # k=10: first rank<=10 is 2021 (rank 8) -> Jan->Jul 2021 = 6 months
        assert cr.lead_times[10] == (date(2021, 1, 1), 6)
        # k=20: still 2021 (rank 8; 2020's rank 40 > 20) -> 6 months
        assert cr.lead_times[20] == (date(2021, 1, 1), 6)
        # k=50: first rank<=50 is 2020 (rank 40) -> Jan 2020 -> Jul 2021 = 18 months
        assert cr.lead_times[50] == (date(2020, 1, 1), 18)

    def test_window_excludes_cutoffs_after_action(self) -> None:
        # A dazzling rank 1 at 2022 must NOT count: it is after the 2021-07
        # action, so it is not "early warning". Lead time stays measured from
        # the pre-action crossings only.
        events = [_non_renewal(date(2021, 7, 1))]
        results = self._results() + [_result(date(2022, 1, 1), [SUB], population=200)]
        cr = compute_case_result(self._CASE, "headline", results, events, DEFAULT_POSITIVE_KINDS)
        assert all(cutoff <= date(2021, 7, 1) for cutoff, _, _ in cr.trajectory)
        assert cr.lead_times[10] == (date(2021, 1, 1), 6)  # unchanged by the post-action rank-1

    def test_never_flagged_is_none_not_zero(self) -> None:
        events = [_non_renewal(date(2021, 7, 1))]
        # ranks always 100 -> never within any k
        never = [
            _result(date(y, 1, 1), ["filler"] * 99 + [SUB], population=200)
            for y in (2018, 2019, 2020, 2021)
        ]
        cr = compute_case_result(self._CASE, "headline", never, events, DEFAULT_POSITIVE_KINDS)
        assert cr.lead_times[10] == (None, None)
        assert cr.lead_times[50] == (None, None)

    def test_no_action_yields_empty_trajectory(self) -> None:
        # fluazinam-under-headline analog: no matching action, nothing to measure
        cr = compute_case_result(
            self._CASE, "headline", self._results(), [], DEFAULT_POSITIVE_KINDS
        )
        assert cr.action_date is None
        assert cr.trajectory == ()
        assert cr.lead_times[10] == (None, None)

    def test_deterministic(self) -> None:
        events = [_non_renewal(date(2021, 7, 1))]
        a = compute_case_result(
            self._CASE, "headline", self._results(), events, DEFAULT_POSITIVE_KINDS
        )
        b = compute_case_result(
            self._CASE, "headline", self._results(), events, DEFAULT_POSITIVE_KINDS
        )
        assert a == b


class TestVerifyLandmarkCas:
    def _graph_with_correct_landmarks(self) -> TemporalGraph:
        g = TemporalGraph()
        for case in LANDMARK_CASES:
            g.add_node(
                Node(
                    id=case.substance_id,
                    type=NodeType.SUBSTANCE,
                    label=case.name,
                    source="s",
                    known_at=date(2010, 1, 1),
                )
            )
        return g

    def test_passes_when_all_match(self) -> None:
        verify_landmark_cas(self._graph_with_correct_landmarks())  # must not raise

    def test_raises_on_label_mismatch(self) -> None:
        # Build fresh with one deliberately-wrong label (add_node keeps the
        # earliest known_at, so overwriting an existing node wouldn't take).
        wrong = LANDMARK_CASES[0]
        g = TemporalGraph()
        for case in LANDMARK_CASES:
            label = "Something Else" if case is wrong else case.name
            g.add_node(
                Node(
                    id=case.substance_id,
                    type=NodeType.SUBSTANCE,
                    label=label,
                    source="s",
                    known_at=date(2010, 1, 1),
                )
            )
        try:
            verify_landmark_cas(g)
        except ValueError as e:
            assert wrong.cas in str(e)
        else:
            raise AssertionError("expected ValueError on label mismatch")

    def test_raises_on_missing_node(self) -> None:
        # Graph missing the first landmark entirely.
        g = TemporalGraph()
        for case in LANDMARK_CASES[1:]:
            g.add_node(
                Node(
                    id=case.substance_id,
                    type=NodeType.SUBSTANCE,
                    label=case.name,
                    source="s",
                    known_at=date(2010, 1, 1),
                )
            )
        try:
            verify_landmark_cas(g)
        except ValueError as e:
            assert "not in graph" in str(e)
        else:
            raise AssertionError("expected ValueError on missing node")
