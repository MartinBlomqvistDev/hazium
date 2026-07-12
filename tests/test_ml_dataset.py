"""build_dataset: population membership, the pre-cutoff-non-renewal censoring
rule, and label correctness.
"""

from datetime import date

from hazium.graph.store import TemporalGraph
from hazium.ml.dataset import FEATURE_COLUMNS, build_dataset
from hazium.models import Node, NodeType, RegulatoryEvent, RegulatoryEventKind

CUTOFF = date(2023, 1, 1)

FLUAZINAM = "substance:cas:79622-59-6"  # dated pre-cutoff fact, no non-renewal
ALREADY_GONE = "substance:cas:11111-11-1"  # non-renewed before cutoff
FUTURE_LOSER = "substance:cas:22222-22-2"  # non-renewed after cutoff -> positive
TOO_NEW = "substance:cas:33333-33-3"  # only a post-cutoff fact -> not in as_of view


def _substance(sid: str, known_at: date) -> Node:
    return Node(id=sid, type=NodeType.SUBSTANCE, label=sid, source="s", known_at=known_at)


def _graph() -> TemporalGraph:
    g = TemporalGraph()
    g.add_node(_substance(FLUAZINAM, date(2015, 1, 1)))
    g.add_node(_substance(ALREADY_GONE, date(2010, 1, 1)))
    g.add_node(_substance(FUTURE_LOSER, date(2010, 1, 1)))
    g.add_node(_substance(TOO_NEW, date(2026, 1, 1)))  # only knowable after cutoff
    return g


def _event(sid: str, kind: RegulatoryEventKind, event_date: date) -> RegulatoryEvent:
    return RegulatoryEvent(
        substance_id=sid,
        kind=kind,
        jurisdiction="EU",
        event_date=event_date,
        source="s",
        known_at=event_date,
    )


class TestPopulation:
    def test_only_substances_with_a_pre_cutoff_fact_are_included(self) -> None:
        X, y, ids = build_dataset(_graph(), [], [], CUTOFF)
        assert TOO_NEW not in ids

    def test_substance_with_pre_cutoff_fact_is_included(self) -> None:
        X, y, ids = build_dataset(_graph(), [], [], CUTOFF)
        assert FLUAZINAM in ids

    def test_already_non_renewed_before_cutoff_is_excluded(self) -> None:
        events = [_event(ALREADY_GONE, RegulatoryEventKind.NON_RENEWAL, date(2020, 1, 1))]
        X, y, ids = build_dataset(_graph(), [], events, CUTOFF)
        assert ALREADY_GONE not in ids

    def test_non_substance_nodes_excluded(self) -> None:
        g = _graph()
        g.add_node(
            Node(
                id="hazard:clp:H400",
                type=NodeType.HAZARD,
                label="H400",
                source="s",
                known_at=date(2010, 1, 1),
            )
        )
        X, y, ids = build_dataset(g, [], [], CUTOFF)
        assert "hazard:clp:H400" not in ids


class TestLabel:
    def test_future_non_renewal_is_positive(self) -> None:
        events = [_event(FUTURE_LOSER, RegulatoryEventKind.NON_RENEWAL, date(2024, 1, 1))]
        X, y, ids = build_dataset(_graph(), [], events, CUTOFF)
        assert y.loc[FUTURE_LOSER] == 1

    def test_exact_cutoff_date_counts_as_future(self) -> None:
        # event_date >= cutoff (not strictly after) is a positive
        events = [_event(FUTURE_LOSER, RegulatoryEventKind.NON_RENEWAL, CUTOFF)]
        X, y, ids = build_dataset(_graph(), [], events, CUTOFF)
        assert y.loc[FUTURE_LOSER] == 1

    def test_no_event_is_negative(self) -> None:
        X, y, ids = build_dataset(_graph(), [], [], CUTOFF)
        assert y.loc[FLUAZINAM] == 0

    def test_approval_event_alone_does_not_make_a_positive(self) -> None:
        events = [_event(FLUAZINAM, RegulatoryEventKind.APPROVAL, date(2009, 1, 1))]
        X, y, ids = build_dataset(_graph(), [], events, CUTOFF)
        assert y.loc[FLUAZINAM] == 0


class TestShape:
    def test_feature_matrix_has_expected_columns(self) -> None:
        X, y, ids = build_dataset(_graph(), [], [], CUTOFF)
        assert list(X.columns) == FEATURE_COLUMNS

    def test_row_count_matches_population(self) -> None:
        X, y, ids = build_dataset(_graph(), [], [], CUTOFF)
        assert len(X) == len(y) == len(ids)

    def test_no_nans_in_feature_matrix(self) -> None:
        X, y, ids = build_dataset(_graph(), [], [], CUTOFF)
        assert not X.isna().any().any()
