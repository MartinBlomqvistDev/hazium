"""Merging EFSA OpenFoodTox structure onto an existing graph, and round-tripping
a graph through JSONL — the two things pipeline 03/04 depend on.
"""

from datetime import date
from pathlib import Path

import pytest

from hazium.graph.build import load_graph, merge_clp, merge_regulatory_events, merge_openfoodtox
from hazium.graph.store import TemporalGraph
from hazium.models import (
    DegradationLink,
    Edge,
    EdgeType,
    HazardClassification,
    Node,
    NodeType,
    RegulatoryEvent,
    RegulatoryEventKind,
    SourceDocument,
    Substance,
)

REGISTER_SNAPSHOT = date(2026, 7, 3)
EFSA_PUBLISHED = date(2026, 4, 30)
CLP_KNOWN_AT = date(2015, 4, 1)

FLUAZINAM_ID = "substance:cas:79622-59-6"
TFA_ID = "substance:cas:76-05-1"
FLUFENACET_ID = "substance:cas:142459-58-3"


def _register_graph() -> TemporalGraph:
    """A minimal graph as build_from_register would leave it: fluazinam only."""
    graph = TemporalGraph()
    graph.add_node(
        Node(
            id=FLUAZINAM_ID,
            type=NodeType.SUBSTANCE,
            label="Fluazinam",
            source="kemi:bkmreg",
            known_at=REGISTER_SNAPSHOT,
        )
    )
    return graph


class TestMergeOpenFoodTox:
    def test_efsa_substance_lands_on_existing_register_node(self) -> None:
        graph = _register_graph()
        merge_openfoodtox(
            graph,
            substances=[
                Substance(
                    name="Fluazinam",
                    cas_number="79622-59-6",
                    source="efsa:openfoodtox",
                    known_at=EFSA_PUBLISHED,
                )
            ],
            degradation_links=[],
            documents=[],
        )
        # add_node keeps the earliest known_at: EFSA's (2026-04) predates
        # the register snapshot (2026-07) in this fixture
        assert graph.node(FLUAZINAM_ID).known_at == EFSA_PUBLISHED
        assert len(graph) == 1  # no duplicate node created

    def test_new_efsa_only_substance_is_added(self) -> None:
        graph = _register_graph()
        merge_openfoodtox(
            graph,
            substances=[
                Substance(
                    name="Trifluoroacetic acid",
                    cas_number="76-05-1",
                    source="efsa:openfoodtox",
                    known_at=EFSA_PUBLISHED,
                )
            ],
            degradation_links=[],
            documents=[],
        )
        assert graph.has_node(TFA_ID)

    def test_degradation_edge_added_between_existing_nodes(self) -> None:
        graph = _register_graph()
        merge_openfoodtox(
            graph,
            substances=[
                Substance(
                    name="Fluazinam", cas_number="79622-59-6", source="s", known_at=EFSA_PUBLISHED
                ),
                Substance(name="TFA", cas_number="76-05-1", source="s", known_at=EFSA_PUBLISHED),
            ],
            degradation_links=[
                DegradationLink(
                    parent_substance_id=FLUAZINAM_ID,
                    metabolite_substance_id=TFA_ID,
                    source="efsa:openfoodtox",
                    known_at=EFSA_PUBLISHED,
                )
            ],
            documents=[],
        )
        paths = graph.evidence_paths(FLUAZINAM_ID, TFA_ID)
        assert any([e.predicate for e in p] == [EdgeType.DEGRADES_TO] for p in paths)

    def test_degradation_link_pulls_both_endpoints_known_at_earlier(self) -> None:
        # Both nodes start at the register snapshot (2026-07-03); a
        # back-dated degradation link (V2a: dated to the parent's earliest
        # EFSA assessment, not the export snapshot) is evidence both
        # substances were knowable much earlier -- mirrors how a dated
        # document already pulls its subject's known_at earlier.
        graph = _register_graph()
        graph.add_node(
            Node(
                id=TFA_ID,
                type=NodeType.SUBSTANCE,
                label="TFA",
                source="kemi:bkmreg",
                known_at=REGISTER_SNAPSHOT,
            )
        )
        earlier = date(2008, 3, 3)
        merge_openfoodtox(
            graph,
            substances=[],
            degradation_links=[
                DegradationLink(
                    parent_substance_id=FLUAZINAM_ID,
                    metabolite_substance_id=TFA_ID,
                    source="efsa:openfoodtox",
                    known_at=earlier,
                )
            ],
            documents=[],
        )
        assert graph.node(FLUAZINAM_ID).known_at == earlier
        assert graph.node(TFA_ID).known_at == earlier

    def test_dated_document_creates_evidence_edge(self) -> None:
        graph = _register_graph()
        merge_openfoodtox(
            graph,
            substances=[],
            degradation_links=[],
            documents=[
                SourceDocument(
                    id="10.2903/j.efsa.2008.137r",
                    title="Conclusion regarding fluazinam",
                    publisher="EFSA",
                    published_at=date(2008, 3, 26),
                    subject_substance_id=FLUAZINAM_ID,
                    source="efsa:openfoodtox",
                    known_at=date(2008, 3, 26),
                )
            ],
        )
        doc_node = graph.node("document:10.2903/j.efsa.2008.137r")
        assert doc_node.type == NodeType.DOCUMENT
        paths = graph.evidence_paths(FLUAZINAM_ID, "document:10.2903/j.efsa.2008.137r")
        assert any([e.predicate for e in p] == [EdgeType.EVIDENCED_BY] for p in paths)

    def test_document_evidence_survives_the_2023_cutoff(self) -> None:
        # the whole point of dated EFSA evidence: it appears in a pre-2023 view
        graph = _register_graph()
        merge_openfoodtox(
            graph,
            substances=[],
            degradation_links=[],
            documents=[
                SourceDocument(
                    id="10.2903/j.efsa.2008.137r",
                    title="Conclusion regarding fluazinam",
                    publisher="EFSA",
                    published_at=date(2008, 3, 26),
                    subject_substance_id=FLUAZINAM_ID,
                    source="efsa:openfoodtox",
                    known_at=date(2008, 3, 26),
                )
            ],
        )
        view = graph.as_of(date(2023, 1, 1))
        assert view.has_node("document:10.2903/j.efsa.2008.137r")
        # the substance itself must also survive: a document dated before the
        # register snapshot is evidence the substance was knowable that early
        assert view.has_node(FLUAZINAM_ID)

    def test_dated_document_pulls_subject_known_at_earlier(self) -> None:
        # fluazinam's node starts at the register snapshot (2026-07-03); a
        # real 2008 EFSA conclusion is evidence it was knowable much earlier
        graph = _register_graph()
        assert graph.node(FLUAZINAM_ID).known_at == REGISTER_SNAPSHOT
        merge_openfoodtox(
            graph,
            substances=[],
            degradation_links=[],
            documents=[
                SourceDocument(
                    id="10.2903/j.efsa.2008.137r",
                    title="Conclusion regarding fluazinam",
                    publisher="EFSA",
                    published_at=date(2008, 3, 26),
                    subject_substance_id=FLUAZINAM_ID,
                    source="efsa:openfoodtox",
                    known_at=date(2008, 3, 26),
                )
            ],
        )
        assert graph.node(FLUAZINAM_ID).known_at == date(2008, 3, 26)

    def test_later_document_does_not_push_known_at_forward(self) -> None:
        # keep-earliest, not overwrite: a later document must never make an
        # already-earlier-known substance look newer
        graph = _register_graph()
        merge_openfoodtox(
            graph,
            substances=[],
            degradation_links=[],
            documents=[
                SourceDocument(
                    id="doc-old",
                    title="Old conclusion",
                    publisher="EFSA",
                    subject_substance_id=FLUAZINAM_ID,
                    source="efsa:openfoodtox",
                    known_at=date(2008, 3, 26),
                ),
                SourceDocument(
                    id="doc-new",
                    title="Newer conclusion",
                    publisher="EFSA",
                    subject_substance_id=FLUAZINAM_ID,
                    source="efsa:openfoodtox",
                    known_at=date(2020, 1, 1),
                ),
            ],
        )
        assert graph.node(FLUAZINAM_ID).known_at == date(2008, 3, 26)

    def test_document_without_subject_creates_no_edge(self) -> None:
        graph = _register_graph()
        merge_openfoodtox(
            graph,
            substances=[],
            degradation_links=[],
            documents=[
                SourceDocument(
                    id="doc-1",
                    title="Some multi-substance opinion",
                    publisher="EFSA",
                    source="efsa:openfoodtox",
                    known_at=EFSA_PUBLISHED,
                )
            ],
        )
        assert graph.has_node("document:doc-1")
        assert graph.edges_of("document:doc-1") == []

    def test_missing_subject_node_raises(self) -> None:
        # subject_substance_id resolved from an index the substances list
        # didn't come from -> a real ingestion inconsistency, must not be silent
        graph = _register_graph()
        with pytest.raises(KeyError):
            merge_openfoodtox(
                graph,
                substances=[],
                degradation_links=[],
                documents=[
                    SourceDocument(
                        id="doc-1",
                        title="Opinion on an unknown substance",
                        publisher="EFSA",
                        subject_substance_id="substance:cas:76-05-1",
                        source="efsa:openfoodtox",
                        known_at=EFSA_PUBLISHED,
                    )
                ],
            )


class TestMergeClp:
    def test_classification_on_existing_substance_creates_hazard_and_edge(self) -> None:
        graph = _register_graph()
        applied, skipped = merge_clp(
            graph,
            [
                HazardClassification(
                    substance_id=FLUAZINAM_ID,
                    hazard_code="H361d",
                    hazard_class="Repr. 2",
                    atp="ATP06",
                    celex="32014R0605",
                    source="echa:clp-annex-vi",
                    known_at=CLP_KNOWN_AT,
                )
            ],
        )
        assert applied == 1
        assert skipped == 0
        hazard_node = graph.node("hazard:clp:H361d")
        assert hazard_node.type == NodeType.HAZARD
        paths = graph.evidence_paths(FLUAZINAM_ID, "hazard:clp:H361d")
        assert any([e.predicate for e in p] == [EdgeType.CLASSIFIED_AS] for p in paths)

    def test_edge_carries_hazard_class_atp_celex_as_attrs(self) -> None:
        graph = _register_graph()
        merge_clp(
            graph,
            [
                HazardClassification(
                    substance_id=FLUAZINAM_ID,
                    hazard_code="H361d",
                    hazard_class="Repr. 2",
                    atp="ATP06",
                    celex="32014R0605",
                    source="echa:clp-annex-vi",
                    known_at=CLP_KNOWN_AT,
                )
            ],
        )
        edge = next(
            e for e in graph.edges_of(FLUAZINAM_ID) if e.predicate == EdgeType.CLASSIFIED_AS
        )
        assert edge.attrs == {"hazard_class": "Repr. 2", "atp": "ATP06", "celex": "32014R0605"}

    def test_classification_for_absent_substance_is_skipped_not_raised(self) -> None:
        graph = _register_graph()
        applied, skipped = merge_clp(
            graph,
            [
                HazardClassification(
                    substance_id="substance:cas:76-05-1",  # TFA, not in this graph
                    hazard_code="H400",
                    source="echa:clp-annex-vi",
                    known_at=CLP_KNOWN_AT,
                )
            ],
        )
        assert applied == 0
        assert skipped == 1
        assert not graph.has_node("hazard:clp:H400")

    def test_classification_survives_pre_2023_cutoff(self) -> None:
        graph = _register_graph()
        merge_clp(
            graph,
            [
                HazardClassification(
                    substance_id=FLUAZINAM_ID,
                    hazard_code="H361d",
                    source="echa:clp-annex-vi",
                    known_at=CLP_KNOWN_AT,
                )
            ],
        )
        view = graph.as_of(date(2023, 1, 1))
        assert view.has_node("hazard:clp:H361d")
        # the substance itself must also survive: without this, the edge is
        # in the view but the north-star ranking has nothing to rank
        assert view.has_node(FLUAZINAM_ID)

    def test_classification_pulls_substance_known_at_earlier(self) -> None:
        # fluazinam's node starts at the register snapshot (2026-07-03); the
        # 2015 CLP classification is evidence it was knowable much earlier
        graph = _register_graph()
        assert graph.node(FLUAZINAM_ID).known_at == REGISTER_SNAPSHOT
        merge_clp(
            graph,
            [
                HazardClassification(
                    substance_id=FLUAZINAM_ID,
                    hazard_code="H361d",
                    source="echa:clp-annex-vi",
                    known_at=CLP_KNOWN_AT,
                )
            ],
        )
        assert graph.node(FLUAZINAM_ID).known_at == CLP_KNOWN_AT

    def test_same_hazard_shared_across_substances_creates_one_node(self) -> None:
        graph = _register_graph()
        graph.add_node(
            Node(
                id=TFA_ID, type=NodeType.SUBSTANCE, label="TFA", source="s", known_at=EFSA_PUBLISHED
            )
        )
        applied, _ = merge_clp(
            graph,
            [
                HazardClassification(
                    substance_id=FLUAZINAM_ID,
                    hazard_code="H400",
                    source="echa:clp-annex-vi",
                    known_at=CLP_KNOWN_AT,
                ),
                HazardClassification(
                    substance_id=TFA_ID,
                    hazard_code="H400",
                    source="echa:clp-annex-vi",
                    known_at=CLP_KNOWN_AT,
                ),
            ],
        )
        assert applied == 2
        hazard_nodes = [n for n in graph.nodes() if n.type == NodeType.HAZARD]
        assert len(hazard_nodes) == 1


class TestMergeRegulatoryEvents:
    def _event(self, kind, event_date, substance_id=FLUAZINAM_ID):
        return RegulatoryEvent(
            substance_id=substance_id,
            kind=kind,
            jurisdiction="EU",
            event_date=event_date,
            source="eu:ppdb",
            known_at=event_date,
        )

    def test_event_creates_node_and_subject_of_edge(self) -> None:
        graph = _register_graph()
        applied, skipped = merge_regulatory_events(
            graph, [self._event(RegulatoryEventKind.NON_RENEWAL, date(2023, 8, 31))]
        )
        assert (applied, skipped) == (1, 0)
        events = [e for e in graph.edges_of(FLUAZINAM_ID) if e.predicate == EdgeType.SUBJECT_OF]
        assert len(events) == 1
        node = graph.node(events[0].object)
        assert node.type == NodeType.REGULATORY_EVENT
        assert node.attrs["kind"] == "non_renewal"

    def test_event_for_absent_substance_is_skipped(self) -> None:
        graph = _register_graph()
        applied, skipped = merge_regulatory_events(
            graph,
            [self._event(RegulatoryEventKind.NON_RENEWAL, date(2023, 8, 31), TFA_ID)],
        )
        assert (applied, skipped) == (0, 1)

    def test_approval_pulls_substance_known_at_earlier(self) -> None:
        # a 2009 approval is proof the substance was knowable in 2009
        graph = _register_graph()
        assert graph.node(FLUAZINAM_ID).known_at == REGISTER_SNAPSHOT
        merge_regulatory_events(
            graph, [self._event(RegulatoryEventKind.APPROVAL, date(2009, 3, 1))]
        )
        assert graph.node(FLUAZINAM_ID).known_at == date(2009, 3, 1)

    def test_non_renewal_survives_its_cutoff_but_not_an_earlier_one(self) -> None:
        graph = _register_graph()
        merge_regulatory_events(
            graph, [self._event(RegulatoryEventKind.NON_RENEWAL, date(2024, 6, 1))]
        )
        event_node = next(
            e.object for e in graph.edges_of(FLUAZINAM_ID) if e.predicate == EdgeType.SUBJECT_OF
        )
        assert graph.as_of(date(2025, 1, 1)).has_node(event_node)
        assert not graph.as_of(date(2024, 1, 1)).has_node(event_node)

    def test_two_events_one_substance_get_distinct_nodes(self) -> None:
        graph = _register_graph()
        applied, _ = merge_regulatory_events(
            graph,
            [
                self._event(RegulatoryEventKind.APPROVAL, date(2009, 3, 1)),
                self._event(RegulatoryEventKind.NON_RENEWAL, date(2023, 8, 31)),
            ],
        )
        assert applied == 2
        event_nodes = [n for n in graph.nodes() if n.type == NodeType.REGULATORY_EVENT]
        assert len(event_nodes) == 2


class TestLoadGraph:
    def test_round_trips_nodes_and_edges(self, tmp_path: Path) -> None:
        graph = _register_graph()
        graph.add_node(
            Node(
                id=TFA_ID, type=NodeType.SUBSTANCE, label="TFA", source="s", known_at=EFSA_PUBLISHED
            )
        )
        graph.add_edge(
            Edge(
                subject=FLUAZINAM_ID,
                predicate=EdgeType.DEGRADES_TO,
                object=TFA_ID,
                source="s",
                known_at=EFSA_PUBLISHED,
            )
        )
        nodes_path, edges_path = tmp_path / "nodes.jsonl", tmp_path / "edges.jsonl"
        nodes_path.write_text(
            "\n".join(n.model_dump_json() for n in graph.nodes()), encoding="utf-8"
        )
        edges_path.write_text(
            "\n".join(e.model_dump_json() for e in graph.edges()), encoding="utf-8"
        )

        reloaded = load_graph(nodes_path, edges_path)
        assert len(reloaded) == len(graph)
        assert reloaded.edge_count == graph.edge_count
        assert reloaded.node(FLUAZINAM_ID).label == "Fluazinam"
