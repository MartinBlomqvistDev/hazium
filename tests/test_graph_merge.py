"""Merging EFSA OpenFoodTox structure onto an existing graph, and round-tripping
a graph through JSONL — the two things pipeline 03/04 depend on.
"""

from datetime import date
from pathlib import Path

import pytest

from hazium.graph.build import load_graph, merge_openfoodtox
from hazium.graph.store import TemporalGraph
from hazium.models import DegradationLink, Edge, EdgeType, Node, NodeType, SourceDocument, Substance

REGISTER_SNAPSHOT = date(2026, 7, 3)
EFSA_PUBLISHED = date(2026, 4, 30)

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
