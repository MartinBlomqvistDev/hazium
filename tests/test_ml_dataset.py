"""build_dataset: population membership, the pre-cutoff-non-renewal censoring
rule, and label correctness.
"""

from datetime import date

from hazium.graph.store import TemporalGraph
from hazium.ml.dataset import (
    EARLY_WARNING_POSITIVE_KINDS,
    FEATURE_COLUMNS,
    approval_age_non_renewal_rates,
    build_dataset,
)
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


class TestPositiveKinds:
    def test_default_kinds_ignore_reevaluation_started(self) -> None:
        events = [_event(FUTURE_LOSER, RegulatoryEventKind.REEVALUATION_STARTED, date(2024, 1, 1))]
        X, y, ids = build_dataset(_graph(), [], events, CUTOFF)
        assert y.loc[FUTURE_LOSER] == 0

    def test_early_warning_kinds_count_reevaluation_started(self) -> None:
        events = [_event(FUTURE_LOSER, RegulatoryEventKind.REEVALUATION_STARTED, date(2024, 1, 1))]
        X, y, ids = build_dataset(
            _graph(), [], events, CUTOFF, positive_kinds=EARLY_WARNING_POSITIVE_KINDS
        )
        assert y.loc[FUTURE_LOSER] == 1

    def test_early_warning_kinds_still_count_non_renewal(self) -> None:
        events = [_event(FUTURE_LOSER, RegulatoryEventKind.NON_RENEWAL, date(2024, 1, 1))]
        X, y, ids = build_dataset(
            _graph(), [], events, CUTOFF, positive_kinds=EARLY_WARNING_POSITIVE_KINDS
        )
        assert y.loc[FUTURE_LOSER] == 1

    def test_pre_cutoff_reevaluation_excludes_from_population_under_broadened_kinds(self) -> None:
        events = [_event(ALREADY_GONE, RegulatoryEventKind.REEVALUATION_STARTED, date(2020, 1, 1))]
        X, y, ids = build_dataset(
            _graph(), [], events, CUTOFF, positive_kinds=EARLY_WARNING_POSITIVE_KINDS
        )
        assert ALREADY_GONE not in ids

    def test_pre_cutoff_reevaluation_does_not_exclude_under_default_kinds(self) -> None:
        # a REEVALUATION_STARTED event is irrelevant to the default label,
        # so it must not trigger the "already realized" censoring either
        events = [_event(ALREADY_GONE, RegulatoryEventKind.REEVALUATION_STARTED, date(2020, 1, 1))]
        X, y, ids = build_dataset(_graph(), [], events, CUTOFF)
        assert ALREADY_GONE in ids


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


class TestApprovalAgeNonRenewalRates:
    """The specific correctness this exists for: an empty oldest band must
    read as "no substances that old exist in the data" (a ceiling of the EU
    approval framework's own start date), never as "100% non-renewed" --
    the two are easy to conflate if `total` isn't reported alongside the rate.
    """

    TODAY = date(2026, 1, 1)

    def _approval(self, sid: str, event_date: date) -> RegulatoryEvent:
        return RegulatoryEvent(
            substance_id=sid,
            kind=RegulatoryEventKind.APPROVAL,
            jurisdiction="EU",
            event_date=event_date,
            source="s",
            known_at=event_date,
        )

    def _non_renewal(self, sid: str, event_date: date) -> RegulatoryEvent:
        return RegulatoryEvent(
            substance_id=sid,
            kind=RegulatoryEventKind.NON_RENEWAL,
            jurisdiction="EU",
            event_date=event_date,
            source="s",
            known_at=event_date,
        )

    def test_still_active_substance_counted_not_non_renewed(self) -> None:
        events = [self._approval("substance:cas:1-1-1", date(2021, 1, 1))]  # 5 years old
        rows = approval_age_non_renewal_rates(events, self.TODAY)
        band = next(r for r in rows if r["age_band"] == "0-9")
        assert band == {
            "age_band": "0-9",
            "total": 1,
            "non_renewed": 0,
            "still_active": 1,
            "non_renewal_rate": 0.0,
        }

    def test_non_renewed_substance_counted_in_its_approval_age_band(self) -> None:
        events = [
            self._approval("substance:cas:2-2-2", date(2011, 1, 1)),  # 15 years old
            self._non_renewal("substance:cas:2-2-2", date(2020, 1, 1)),
        ]
        rows = approval_age_non_renewal_rates(events, self.TODAY)
        band = next(r for r in rows if r["age_band"] == "10-19")
        assert band["total"] == 1
        assert band["non_renewed"] == 1
        assert band["non_renewal_rate"] == 1.0

    def test_empty_band_has_none_rate_not_zero_division(self) -> None:
        # nothing approved anywhere near 30+ years ago -- the exact real
        # situation this function was written to report honestly
        events = [self._approval("substance:cas:3-3-3", date(2021, 1, 1))]
        rows = approval_age_non_renewal_rates(events, self.TODAY)
        band = next(r for r in rows if r["age_band"] == "30+")
        assert band["total"] == 0
        assert band["non_renewal_rate"] is None

    def test_earliest_approval_used_when_multiple_exist(self) -> None:
        # a substance re-approved after a renewal is still aged from its
        # FIRST approval, matching eu_regulatory_features' own definition
        events = [
            self._approval("substance:cas:4-4-4", date(2011, 1, 1)),  # first, 15y old
            self._approval("substance:cas:4-4-4", date(2018, 1, 1)),  # later renewal
        ]
        rows = approval_age_non_renewal_rates(events, self.TODAY)
        assert next(r for r in rows if r["age_band"] == "10-19")["total"] == 1
        assert next(r for r in rows if r["age_band"] == "0-9")["total"] == 0

    def test_substance_with_no_approval_event_is_not_counted_anywhere(self) -> None:
        events = [self._non_renewal("substance:cas:5-5-5", date(2020, 1, 1))]
        rows = approval_age_non_renewal_rates(events, self.TODAY)
        assert sum(r["total"] for r in rows) == 0

    def test_all_bands_present_even_when_empty(self) -> None:
        rows = approval_age_non_renewal_rates([], self.TODAY)
        assert [r["age_band"] for r in rows] == ["0-9", "10-19", "20-29", "30+"]
        assert all(r["total"] == 0 for r in rows)
