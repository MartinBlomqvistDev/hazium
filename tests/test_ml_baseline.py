"""XGBoost scoring wiring: out-of-fold vs. fallback, and evaluate_cutoff shape.

Keeps XGBoost fits small (few estimators via make_model's own default is
already cheap at this row count) -- these tests care about wiring, not model
quality.
"""

from datetime import date

import numpy as np
import pandas as pd

from hazium.graph.store import TemporalGraph
from hazium.ml.baseline import (
    TRIVIAL_BASELINES,
    evaluate_cutoff,
    evaluate_cutoff_with_embeddings,
    score_xgboost,
)
from hazium.ml.dataset import EARLY_WARNING_POSITIVE_KINDS, FEATURE_COLUMNS
from hazium.models import Edge, EdgeType, Node, NodeType, RegulatoryEvent, RegulatoryEventKind

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


class TestEvaluateCutoffWithEmbeddings:
    """V2b's three-condition comparison, and its one hard correctness
    requirement: the embedding must be blind to anything dated `>= cutoff`.
    """

    _SUBSTANCES = [
        ("substance:cas:79622-59-6", date(2015, 1, 1)),  # fluazinam
        ("substance:cas:142459-58-3", date(2004, 1, 1)),  # flufenacet
        ("substance:cas:76-05-1", date(2008, 1, 1)),  # TFA
        ("substance:cas:11111-11-1", date(2010, 1, 1)),
        ("substance:cas:22222-22-2", date(2012, 1, 1)),
        ("substance:cas:33333-33-3", date(2011, 1, 1)),
    ]

    def _graph(self) -> TemporalGraph:
        g = TemporalGraph()
        for sid, known_at in self._SUBSTANCES:
            g.add_node(
                Node(id=sid, type=NodeType.SUBSTANCE, label=sid, source="s", known_at=known_at)
            )
        g.add_node(
            Node(
                id="hazard:clp:H410",
                type=NodeType.HAZARD,
                label="H410",
                source="s",
                known_at=date(2010, 1, 1),
            )
        )
        # Pre-cutoff informative structure: one degradation edge, two
        # substances sharing a hazard.
        g.add_edge(
            Edge(
                subject="substance:cas:142459-58-3",
                predicate=EdgeType.DEGRADES_TO,
                object="substance:cas:76-05-1",
                source="s",
                known_at=date(2008, 3, 3),
            )
        )
        for sid in ("substance:cas:79622-59-6", "substance:cas:11111-11-1"):
            g.add_edge(
                Edge(
                    subject=sid,
                    predicate=EdgeType.CLASSIFIED_AS,
                    object="hazard:clp:H410",
                    source="s",
                    known_at=date(2012, 1, 1),
                )
            )
        return g

    def _events(self) -> list[RegulatoryEvent]:
        return [
            RegulatoryEvent(
                substance_id="substance:cas:22222-22-2",
                kind=RegulatoryEventKind.NON_RENEWAL,
                jurisdiction="EU",
                event_date=date(2024, 1, 1),
                source="s",
                known_at=date(2024, 1, 1),
            ),
            RegulatoryEvent(
                substance_id="substance:cas:33333-33-3",
                kind=RegulatoryEventKind.NON_RENEWAL,
                jurisdiction="EU",
                event_date=date(2024, 6, 1),
                source="s",
                known_at=date(2024, 6, 1),
            ),
        ]

    def test_includes_trivial_plus_three_xgboost_conditions(self) -> None:
        result = evaluate_cutoff_with_embeddings(self._graph(), [], self._events(), CUTOFF)
        assert set(result.scores.keys()) == set(TRIVIAL_BASELINES) | {
            "xgboost_tabular",
            "xgboost_embed_only",
            "xgboost_tabular_plus_embed",
        }

    def test_all_score_arrays_match_population_length(self) -> None:
        result = evaluate_cutoff_with_embeddings(self._graph(), [], self._events(), CUTOFF)
        for scores in result.scores.values():
            assert len(scores) == result.population

    def test_embedding_scores_invariant_to_facts_dated_on_or_after_cutoff(self) -> None:
        # The temporal-refit correctness test V2_SCOPE.md calls for: perturb
        # the graph with a *post-cutoff* degrades_to edge between two
        # population members, and confirm every score (embedding included)
        # is byte-identical to the unperturbed run -- proof the embedding
        # never saw it, because evaluate_cutoff_with_embeddings refits on
        # graph.as_of(cutoff) fresh, every call.
        baseline_graph = self._graph()
        baseline_result = evaluate_cutoff_with_embeddings(
            baseline_graph, [], self._events(), CUTOFF
        )

        perturbed_graph = self._graph()
        perturbed_graph.add_edge(
            Edge(
                subject="substance:cas:22222-22-2",
                predicate=EdgeType.DEGRADES_TO,
                object="substance:cas:33333-33-3",
                source="s",
                known_at=date(2024, 1, 1),  # dated >= CUTOFF: must not leak in
            )
        )
        perturbed_result = evaluate_cutoff_with_embeddings(
            perturbed_graph, [], self._events(), CUTOFF
        )

        assert baseline_result.ids == perturbed_result.ids
        for name in baseline_result.scores:
            assert (baseline_result.scores[name] == perturbed_result.scores[name]).all(), name
