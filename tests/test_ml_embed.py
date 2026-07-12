"""Metapath2vec: hand-built views (embed.py takes a view directly, like
ml/features.py -- tests build the view exactly as as_of would).
"""

from datetime import date

from hazium.graph.store import TemporalGraph
from hazium.ml.embed import (
    _random_walk,
    _walk_neighbors,
    embedding_dataframe,
    fit_metapath2vec,
    generate_walks,
)
from hazium.models import Edge, EdgeType, Node, NodeType

KNOWN_AT = date(2015, 1, 1)

FLUFENACET = "substance:cas:142459-58-3"
TFA = "substance:cas:76-05-1"
FLUAZINAM = "substance:cas:79622-59-6"
HAZARD_H410 = "hazard:clp:H410"
DOC = "document:doc-1"


def _node(node_id: str, node_type: NodeType) -> Node:
    return Node(id=node_id, type=node_type, label=node_id, source="s", known_at=KNOWN_AT)


def _edge(subject: str, predicate: EdgeType, obj: str) -> Edge:
    return Edge(subject=subject, predicate=predicate, object=obj, source="s", known_at=KNOWN_AT)


def _degrades_hazard_view() -> TemporalGraph:
    """FLUFENACET -degrades_to- TFA; FLUFENACET & FLUAZINAM share H410;
    FLUAZINAM -evidenced_by- DOC (an uninformative edge type for the walk).
    """
    view = TemporalGraph()
    for node_id, node_type in (
        (FLUFENACET, NodeType.SUBSTANCE),
        (TFA, NodeType.SUBSTANCE),
        (FLUAZINAM, NodeType.SUBSTANCE),
        (HAZARD_H410, NodeType.HAZARD),
        (DOC, NodeType.DOCUMENT),
    ):
        view.add_node(_node(node_id, node_type))
    view.add_edge(_edge(FLUFENACET, EdgeType.DEGRADES_TO, TFA))
    view.add_edge(_edge(FLUFENACET, EdgeType.CLASSIFIED_AS, HAZARD_H410))
    view.add_edge(_edge(FLUAZINAM, EdgeType.CLASSIFIED_AS, HAZARD_H410))
    view.add_edge(_edge(FLUAZINAM, EdgeType.EVIDENCED_BY, DOC))
    return view


class TestWalkNeighbors:
    def test_degrades_to_neighbor_included(self) -> None:
        view = _degrades_hazard_view()
        assert TFA in _walk_neighbors(view, FLUFENACET)

    def test_shared_hazard_reachable_via_hazard_node(self) -> None:
        view = _degrades_hazard_view()
        assert HAZARD_H410 in _walk_neighbors(view, FLUFENACET)
        assert FLUFENACET in _walk_neighbors(view, HAZARD_H410)
        assert FLUAZINAM in _walk_neighbors(view, HAZARD_H410)

    def test_evidenced_by_excluded(self) -> None:
        view = _degrades_hazard_view()
        assert DOC not in _walk_neighbors(view, FLUAZINAM)

    def test_isolated_node_has_no_neighbors(self) -> None:
        view = TemporalGraph()
        view.add_node(_node("substance:cas:1-1-1", NodeType.SUBSTANCE))
        assert _walk_neighbors(view, "substance:cas:1-1-1") == []


class TestRandomWalk:
    def test_stops_early_when_stuck(self) -> None:
        import random

        view = TemporalGraph()
        view.add_node(_node("substance:cas:1-1-1", NodeType.SUBSTANCE))
        walk = _random_walk(view, "substance:cas:1-1-1", length=10, rng=random.Random(0))
        assert walk == ["substance:cas:1-1-1"]

    def test_walk_starts_at_given_node(self) -> None:
        import random

        view = _degrades_hazard_view()
        walk = _random_walk(view, FLUFENACET, length=5, rng=random.Random(0))
        assert walk[0] == FLUFENACET

    def test_walk_only_visits_reachable_via_informative_edges(self) -> None:
        import random

        view = _degrades_hazard_view()
        walk = _random_walk(view, FLUFENACET, length=20, rng=random.Random(0))
        assert DOC not in walk


class TestGenerateWalks:
    def test_deterministic_given_same_seed(self) -> None:
        view = _degrades_hazard_view()
        ids = [FLUFENACET, TFA, FLUAZINAM]
        walks_a = generate_walks(view, ids, walk_length=10, num_walks=3, seed=7)
        walks_b = generate_walks(view, ids, walk_length=10, num_walks=3, seed=7)
        assert walks_a == walks_b

    def test_different_seed_can_differ(self) -> None:
        # Not a strict guarantee for tiny fixtures, but with 3+ walks over a
        # branching graph the two seeds should not coincidentally match.
        view = _degrades_hazard_view()
        ids = [FLUFENACET, TFA, FLUAZINAM]
        walks_a = generate_walks(view, ids, walk_length=10, num_walks=5, seed=1)
        walks_b = generate_walks(view, ids, walk_length=10, num_walks=5, seed=2)
        assert walks_a != walks_b

    def test_input_order_does_not_affect_output(self) -> None:
        view = _degrades_hazard_view()
        forward = generate_walks(view, [FLUFENACET, TFA, FLUAZINAM], seed=3)
        reversed_order = generate_walks(view, [FLUAZINAM, TFA, FLUFENACET], seed=3)
        assert forward == reversed_order

    def test_one_walk_per_num_walks_per_substance(self) -> None:
        view = _degrades_hazard_view()
        walks = generate_walks(view, [FLUFENACET, TFA], num_walks=4, seed=1)
        assert len(walks) == 8


class TestFitMetapath2Vec:
    def test_returns_vector_of_requested_dim(self) -> None:
        view = _degrades_hazard_view()
        vectors = fit_metapath2vec(view, [FLUFENACET, TFA, FLUAZINAM], dim=8, seed=1)
        for vec in vectors.values():
            assert vec.shape == (8,)

    def test_deterministic_given_same_view_and_seed(self) -> None:
        view = _degrades_hazard_view()
        ids = [FLUFENACET, TFA, FLUAZINAM]
        vectors_a = fit_metapath2vec(view, ids, dim=8, seed=42)
        vectors_b = fit_metapath2vec(view, ids, dim=8, seed=42)
        assert vectors_a.keys() == vectors_b.keys()
        for key in vectors_a:
            assert (vectors_a[key] == vectors_b[key]).all()

    def test_isolated_substance_absent_from_result(self) -> None:
        view = _degrades_hazard_view()
        view.add_node(_node("substance:cas:9-9-9", NodeType.SUBSTANCE))
        vectors = fit_metapath2vec(
            view, [FLUFENACET, TFA, FLUAZINAM, "substance:cas:9-9-9"], dim=8, seed=1
        )
        assert "substance:cas:9-9-9" not in vectors

    def test_no_informative_edges_at_all_yields_empty(self) -> None:
        view = TemporalGraph()
        view.add_node(_node("substance:cas:1-1-1", NodeType.SUBSTANCE))
        assert fit_metapath2vec(view, ["substance:cas:1-1-1"], dim=8, seed=1) == {}


class TestEmbeddingDataframe:
    def test_shape_and_columns(self) -> None:
        vectors = {FLUFENACET: [1.0] * 4}
        df = embedding_dataframe(vectors, [FLUFENACET, TFA], dim=4)
        assert list(df.columns) == ["emb_0", "emb_1", "emb_2", "emb_3"]
        assert list(df.index) == [FLUFENACET, TFA]

    def test_missing_substance_gets_zero_vector(self) -> None:
        vectors = {FLUFENACET: [1.0, 2.0]}
        df = embedding_dataframe(vectors, [FLUFENACET, TFA], dim=2)
        assert list(df.loc[TFA]) == [0.0, 0.0]
        assert list(df.loc[FLUFENACET]) == [1.0, 2.0]
