"""XGBoost scoring wiring: out-of-fold vs. fallback, and evaluate_cutoff shape.

Keeps XGBoost fits small (few estimators via make_model's own default is
already cheap at this row count) -- these tests care about wiring, not model
quality.
"""

from datetime import date

import numpy as np
import pandas as pd

from hazium.graph.store import TemporalGraph
from hazium.ml.baseline import TRIVIAL_BASELINES, evaluate_cutoff, score_xgboost
from hazium.ml.dataset import EARLY_WARNING_POSITIVE_KINDS, FEATURE_COLUMNS
from hazium.models import Node, NodeType, RegulatoryEvent, RegulatoryEventKind

CUTOFF = date(2023, 1, 1)


def _toy_dataset(n: int, n_pos: int) -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(0)
    X = pd.DataFrame(
        rng.random((n, len(FEATURE_COLUMNS))),
        columns=FEATURE_COLUMNS,
        index=[f"s{i}" for i in range(n)],
    )
    y = pd.Series([1] * n_pos + [0] * (n - n_pos), index=X.index, name="label")
    return X, y


class TestScoreXgboost:
    def test_output_length_matches_input(self) -> None:
        X, y = _toy_dataset(20, 5)
        scores, _ = score_xgboost(X, y)
        assert len(scores) == 20

    def test_scores_are_probabilities(self) -> None:
        X, y = _toy_dataset(20, 5)
        scores, _ = score_xgboost(X, y)
        assert ((scores >= 0) & (scores <= 1)).all()

    def test_enough_positives_uses_out_of_fold(self) -> None:
        X, y = _toy_dataset(20, 5)
        _, out_of_fold = score_xgboost(X, y)
        assert out_of_fold is True

    def test_too_few_positives_falls_back_to_in_sample(self) -> None:
        X, y = _toy_dataset(10, 1)
        _, out_of_fold = score_xgboost(X, y)
        assert out_of_fold is False

    def test_zero_positives_falls_back_without_raising(self) -> None:
        X, y = _toy_dataset(10, 0)
        scores, out_of_fold = score_xgboost(X, y)
        assert out_of_fold is False
        assert len(scores) == 10


class TestEvaluateCutoff:
    def _graph(self) -> TemporalGraph:
        g = TemporalGraph()
        g.add_node(
            Node(
                id="substance:cas:79622-59-6",
                type=NodeType.SUBSTANCE,
                label="Fluazinam",
                source="s",
                known_at=date(2015, 1, 1),
            )
        )
        g.add_node(
            Node(
                id="substance:cas:11111-11-1",
                type=NodeType.SUBSTANCE,
                label="Other",
                source="s",
                known_at=date(2010, 1, 1),
            )
        )
        return g

    def test_includes_all_trivial_baselines_plus_xgboost(self) -> None:
        result = evaluate_cutoff(self._graph(), [], [], CUTOFF)
        assert set(result.scores.keys()) == set(TRIVIAL_BASELINES) | {"xgboost"}

    def test_population_and_positives_counts(self) -> None:
        events = [
            RegulatoryEvent(
                substance_id="substance:cas:11111-11-1",
                kind=RegulatoryEventKind.NON_RENEWAL,
                jurisdiction="EU",
                event_date=date(2024, 1, 1),
                source="s",
                known_at=date(2024, 1, 1),
            )
        ]
        result = evaluate_cutoff(self._graph(), [], events, CUTOFF)
        assert result.population == 2
        assert result.positives == 1

    def test_positive_kinds_broadens_the_label(self) -> None:
        events = [
            RegulatoryEvent(
                substance_id="substance:cas:11111-11-1",
                kind=RegulatoryEventKind.REEVALUATION_STARTED,
                jurisdiction="SE",
                event_date=date(2024, 1, 1),
                source="s",
                known_at=date(2024, 1, 1),
            )
        ]
        default_result = evaluate_cutoff(self._graph(), [], events, CUTOFF)
        broadened_result = evaluate_cutoff(
            self._graph(), [], events, CUTOFF, positive_kinds=EARLY_WARNING_POSITIVE_KINDS
        )
        assert default_result.positives == 0
        assert broadened_result.positives == 1

    def test_all_score_arrays_match_population_length(self) -> None:
        result = evaluate_cutoff(self._graph(), [], [], CUTOFF)
        for scores in result.scores.values():
            assert len(scores) == result.population
