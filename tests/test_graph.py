"""Temporal graph semantics, exercised on a miniature fluazinam evidence graph.

The fixture mirrors the real case: fluazinam approved in Sweden (2008),
sold in a fungicide used on potatoes, known to degrade to TFA (2021),
under EFSA re-evaluation (2024), subject of national media scrutiny (2026).
"""

from datetime import date

import pytest

from hazium.graph.store import TemporalGraph
from hazium.models import Edge, EdgeType, Node, NodeType

FLUAZINAM = "substance:cas:79622-59-6"
TFA = "substance:cas:76-05-1"
PRODUCT = "product:se:shirlan"
POTATO = "crop:agrovoc:potato"
SWEDEN = "country:SE"
REEVAL = "regulatory_event:eu:fluazinam-reeval-2024"
SVT_DOC = "document:svt:fluazinam-2026"

CUTOFF = date(2023, 1, 1)


def _node(node_id: str, node_type: NodeType, known_at: date) -> Node:
    return Node(id=node_id, type=node_type, label=node_id, source="test", known_at=known_at)


def _edge(subject: str, predicate: EdgeType, obj: str, known_at: date) -> Edge:
    return Edge(subject=subject, predicate=predicate, object=obj, source="test", known_at=known_at)


@pytest.fixture()
def graph() -> TemporalGraph:
    g = TemporalGraph()
    g.add_node(_node(FLUAZINAM, NodeType.SUBSTANCE, date(2008, 1, 1)))
    g.add_node(_node(TFA, NodeType.SUBSTANCE, date(2008, 1, 1)))
    g.add_node(_node(PRODUCT, NodeType.PRODUCT, date(2008, 1, 1)))
    g.add_node(_node(POTATO, NodeType.CROP, date(2008, 1, 1)))
    g.add_node(_node(SWEDEN, NodeType.COUNTRY, date(2008, 1, 1)))
    g.add_node(_node(REEVAL, NodeType.REGULATORY_EVENT, date(2024, 3, 1)))
    g.add_node(_node(SVT_DOC, NodeType.DOCUMENT, date(2026, 6, 1)))

    g.add_edge(_edge(FLUAZINAM, EdgeType.APPROVED_IN, SWEDEN, date(2008, 1, 1)))
    g.add_edge(_edge(PRODUCT, EdgeType.CONTAINS, FLUAZINAM, date(2008, 1, 1)))
    g.add_edge(_edge(PRODUCT, EdgeType.USED_ON, POTATO, date(2008, 1, 1)))
    g.add_edge(_edge(FLUAZINAM, EdgeType.DEGRADES_TO, TFA, date(2021, 6, 1)))
    g.add_edge(_edge(FLUAZINAM, EdgeType.SUBJECT_OF, REEVAL, date(2024, 3, 1)))
    g.add_edge(_edge(FLUAZINAM, EdgeType.EVIDENCED_BY, SVT_DOC, date(2026, 6, 1)))
    return g


class TestTemporalView:
    def test_cutoff_excludes_later_facts(self, graph: TemporalGraph) -> None:
        view = graph.as_of(CUTOFF)
        predicates = {e.predicate for e in view.edges_of(FLUAZINAM)}
        assert EdgeType.SUBJECT_OF not in predicates
        assert EdgeType.EVIDENCED_BY not in predicates

    def test_cutoff_keeps_earlier_facts(self, graph: TemporalGraph) -> None:
        view = graph.as_of(CUTOFF)
        predicates = {e.predicate for e in view.edges_of(FLUAZINAM)}
        assert {EdgeType.APPROVED_IN, EdgeType.CONTAINS, EdgeType.DEGRADES_TO} <= predicates

    def test_cutoff_is_strict(self, graph: TemporalGraph) -> None:
        view = graph.as_of(date(2024, 3, 1))
        predicates = {e.predicate for e in view.edges_of(FLUAZINAM)}
        assert EdgeType.SUBJECT_OF not in predicates  # known_at == cutoff is excluded

    def test_view_drops_orphaned_nodes_edges(self, graph: TemporalGraph) -> None:
        view = graph.as_of(CUTOFF)
        with pytest.raises(KeyError):
            view.node(SVT_DOC)


class TestEvidencePaths:
    def test_degradation_path_exists_before_cutoff(self, graph: TemporalGraph) -> None:
        paths = graph.as_of(CUTOFF).evidence_paths(FLUAZINAM, TFA)
        assert [e.predicate for e in paths[0]] == [EdgeType.DEGRADES_TO]

    def test_undirected_traversal_reaches_crop(self, graph: TemporalGraph) -> None:
        paths = graph.evidence_paths(FLUAZINAM, POTATO)
        assert any([e.predicate for e in p] == [EdgeType.CONTAINS, EdgeType.USED_ON] for p in paths)

    def test_missing_endpoint_yields_no_paths(self, graph: TemporalGraph) -> None:
        assert graph.evidence_paths(FLUAZINAM, "substance:cas:50-00-0") == []


def test_edges_never_create_nodes(graph: TemporalGraph) -> None:
    with pytest.raises(KeyError):
        graph.add_edge(_edge(FLUAZINAM, EdgeType.DEGRADES_TO, "substance:name:ghost", CUTOFF))
