"""Feature functions: hand-built views (features.py takes a view directly,
not a full graph + cutoff, so tests build the view exactly as as_of would).
"""

from datetime import date

from hazium.graph.store import TemporalGraph
from hazium.ml.features import (
    clp_features,
    efsa_features,
    eu_regulatory_features,
    graph_structural_features,
    sales_features,
)
from hazium.models import (
    Edge,
    EdgeType,
    Node,
    NodeType,
    RegulatoryEvent,
    RegulatoryEventKind,
    SalesRecord,
)

CUTOFF = date(2023, 1, 1)
FLUAZINAM = "substance:cas:79622-59-6"
TFA = "substance:cas:76-05-1"


def _substance_node(sid: str, known_at: date) -> Node:
    return Node(id=sid, type=NodeType.SUBSTANCE, label=sid, source="s", known_at=known_at)


def _hazard_node(code: str, known_at: date) -> Node:
    return Node(
        id=f"hazard:clp:{code}", type=NodeType.HAZARD, label=code, source="s", known_at=known_at
    )


class TestClpFeatures:
    def test_no_classifications_yields_zeros(self) -> None:
        view = TemporalGraph()
        view.add_node(_substance_node(FLUAZINAM, date(2015, 1, 1)))
        f = clp_features(view, FLUAZINAM, CUTOFF)
        assert f["clp_n_hazard_codes"] == 0.0
        assert f["clp_has_cmr"] == 0.0

    def test_cmr_and_aquatic_chronic_flags(self) -> None:
        view = TemporalGraph()
        view.add_node(_substance_node(FLUAZINAM, date(2015, 4, 1)))
        for code in ("H361d", "H410"):
            view.add_node(_hazard_node(code, date(2015, 4, 1)))
            view.add_edge(
                Edge(
                    subject=FLUAZINAM,
                    predicate=EdgeType.CLASSIFIED_AS,
                    object=f"hazard:clp:{code}",
                    source="echa:clp-annex-vi",
                    known_at=date(2015, 4, 1),
                    attrs={"atp": "ATP06"},
                )
            )
        f = clp_features(view, FLUAZINAM, CUTOFF)
        assert f["clp_n_hazard_codes"] == 2.0
        assert f["clp_n_distinct_atp"] == 1.0
        assert f["clp_has_cmr"] == 1.0
        assert f["clp_has_aquatic_chronic_1"] == 1.0
        assert f["clp_has_stot"] == 0.0
        assert f["clp_years_since_last_classification"] == CUTOFF.year - 2015

    def test_only_edges_from_this_substance_are_counted(self) -> None:
        view = TemporalGraph()
        view.add_node(_substance_node(FLUAZINAM, date(2015, 1, 1)))
        view.add_node(_substance_node(TFA, date(2015, 1, 1)))
        view.add_node(_hazard_node("H400", date(2015, 1, 1)))
        view.add_edge(
            Edge(
                subject=TFA,
                predicate=EdgeType.CLASSIFIED_AS,
                object="hazard:clp:H400",
                source="s",
                known_at=date(2015, 1, 1),
            )
        )
        f = clp_features(view, FLUAZINAM, CUTOFF)
        assert f["clp_n_hazard_codes"] == 0.0


class TestEfsaFeatures:
    def test_no_assessments_yields_zeros(self) -> None:
        view = TemporalGraph()
        view.add_node(_substance_node(FLUAZINAM, date(2015, 1, 1)))
        f = efsa_features(view, FLUAZINAM, CUTOFF)
        assert f["efsa_n_assessments"] == 0.0

    def test_span_and_recency(self) -> None:
        view = TemporalGraph()
        view.add_node(_substance_node(FLUAZINAM, date(2008, 1, 1)))
        view.add_node(
            Node(
                id="document:d1",
                type=NodeType.DOCUMENT,
                label="d1",
                source="s",
                known_at=date(2008, 3, 26),
            )
        )
        view.add_node(
            Node(
                id="document:d2",
                type=NodeType.DOCUMENT,
                label="d2",
                source="s",
                known_at=date(2018, 6, 1),
            )
        )
        for doc, known_at in (
            ("document:d1", date(2008, 3, 26)),
            ("document:d2", date(2018, 6, 1)),
        ):
            view.add_edge(
                Edge(
                    subject=FLUAZINAM,
                    predicate=EdgeType.EVIDENCED_BY,
                    object=doc,
                    source="s",
                    known_at=known_at,
                )
            )
        f = efsa_features(view, FLUAZINAM, CUTOFF)
        assert f["efsa_n_assessments"] == 2.0
        assert f["efsa_assessment_span_years"] == 10.0
        assert f["efsa_years_since_last"] == CUTOFF.year - 2018


class TestSalesFeatures:
    def _record(self, year: int, tonnes: float, known_at: date) -> SalesRecord:
        return SalesRecord(
            substance_id=FLUAZINAM,
            country="SE",
            year=year,
            tonnes_active_substance=tonnes,
            source="kemi:sales",
            known_at=known_at,
        )

    def test_no_records_yields_zeros(self) -> None:
        f = sales_features(FLUAZINAM, [], CUTOFF)
        assert f["sales_latest_tonnage"] == 0.0
        assert f["sales_years_on_market"] == 0.0

    def test_post_cutoff_records_excluded(self) -> None:
        records = [self._record(2024, 100.0, date(2025, 1, 1))]
        f = sales_features(FLUAZINAM, records, CUTOFF)
        assert f["sales_latest_tonnage"] == 0.0

    def test_pre_cutoff_records_used_latest_by_year(self) -> None:
        records = [
            self._record(2019, 10.0, date(2020, 1, 1)),
            self._record(2021, 20.0, date(2022, 1, 1)),
        ]
        f = sales_features(FLUAZINAM, records, CUTOFF)
        assert f["sales_latest_tonnage"] == 20.0
        assert f["sales_years_on_market"] == 2.0

    def test_other_substance_records_excluded(self) -> None:
        records = [
            SalesRecord(
                substance_id=TFA,
                country="SE",
                year=2020,
                tonnes_active_substance=5.0,
                source="s",
                known_at=date(2021, 1, 1),
            )
        ]
        f = sales_features(FLUAZINAM, records, CUTOFF)
        assert f["sales_latest_tonnage"] == 0.0


class TestGraphStructuralFeatures:
    def test_shared_hazard_neighbour_counted(self) -> None:
        view = TemporalGraph()
        for sid in (FLUAZINAM, TFA):
            view.add_node(_substance_node(sid, date(2015, 1, 1)))
        view.add_node(_hazard_node("H400", date(2015, 1, 1)))
        for sid in (FLUAZINAM, TFA):
            view.add_edge(
                Edge(
                    subject=sid,
                    predicate=EdgeType.CLASSIFIED_AS,
                    object="hazard:clp:H400",
                    source="s",
                    known_at=date(2015, 1, 1),
                )
            )
        f = graph_structural_features(view, FLUAZINAM)
        assert f["graph_shared_hazard_substance_count"] == 1.0
        assert f["graph_degree"] == 1.0

    def test_no_edges_yields_zero_degree(self) -> None:
        view = TemporalGraph()
        view.add_node(_substance_node(FLUAZINAM, date(2015, 1, 1)))
        f = graph_structural_features(view, FLUAZINAM)
        assert f["graph_degree"] == 0.0
        assert f["graph_shared_hazard_substance_count"] == 0.0
        assert f["graph_metabolite_degree"] == 0.0

    def test_metabolite_degree_counts_degrades_to_either_direction(self) -> None:
        # Mirrors the real graph: FLUAZINAM has no degradation edge at all
        # (verified 2026-07-11 and again in V2a); a substance that *does*
        # degrade (here standing in for flufenacet) gets a nonzero degree
        # whether it is the parent or the metabolite of the edge.
        parent = "substance:cas:142459-58-3"
        view = TemporalGraph()
        for sid in (parent, TFA):
            view.add_node(_substance_node(sid, date(2008, 1, 1)))
        view.add_edge(
            Edge(
                subject=parent,
                predicate=EdgeType.DEGRADES_TO,
                object=TFA,
                source="efsa:openfoodtox",
                known_at=date(2008, 3, 3),
            )
        )
        assert graph_structural_features(view, parent)["graph_metabolite_degree"] == 1.0
        assert graph_structural_features(view, TFA)["graph_metabolite_degree"] == 1.0
        assert graph_structural_features(view, FLUAZINAM)["graph_metabolite_degree"] == 0.0


class TestEuRegulatoryFeatures:
    def _event(self, kind: RegulatoryEventKind, event_date: date) -> RegulatoryEvent:
        return RegulatoryEvent(
            substance_id=FLUAZINAM,
            kind=kind,
            jurisdiction="EU",
            event_date=event_date,
            source="eu:ppdb",
            known_at=event_date,
        )

    def test_no_events_yields_zeros(self) -> None:
        f = eu_regulatory_features(FLUAZINAM, [], CUTOFF)
        assert f["eu_has_approval"] == 0.0

    def test_pre_cutoff_approval_used(self) -> None:
        events = [self._event(RegulatoryEventKind.APPROVAL, date(2009, 3, 1))]
        f = eu_regulatory_features(FLUAZINAM, events, CUTOFF)
        assert f["eu_has_approval"] == 1.0
        assert f["eu_years_since_first_approval"] == CUTOFF.year - 2009

    def test_post_cutoff_approval_excluded(self) -> None:
        events = [self._event(RegulatoryEventKind.APPROVAL, date(2024, 1, 1))]
        f = eu_regulatory_features(FLUAZINAM, events, CUTOFF)
        assert f["eu_has_approval"] == 0.0

    def test_other_substance_events_excluded(self) -> None:
        events = [
            RegulatoryEvent(
                substance_id=TFA,
                kind=RegulatoryEventKind.APPROVAL,
                jurisdiction="EU",
                event_date=date(2009, 1, 1),
                source="s",
                known_at=date(2009, 1, 1),
            )
        ]
        f = eu_regulatory_features(FLUAZINAM, events, CUTOFF)
        assert f["eu_has_approval"] == 0.0
