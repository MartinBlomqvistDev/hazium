"""Tests for the two-hop evidence mesh.

The load-bearing test is ``test_mesh_frames_match_as_of_reachability``: the mesh is
a compressed re-expression of repeated ``as_of`` views, so it is only correct if it
reproduces them exactly. Everything else guards a boundary that would otherwise
silently shift evidence a year early, which on this project is the difference
between a temporal claim and a leak.
"""

from __future__ import annotations

from datetime import date

import pytest

from hazium.graph.store import TemporalGraph
from hazium.models import Edge, EdgeType, Node, NodeType

CUTOFFS = [date(y, 1, 1) for y in range(2009, 2025)]
CENTRE = "substance:c"


def _node(node_id: str, known: date, ntype: NodeType = NodeType.SUBSTANCE, label: str = "") -> Node:
    return Node(
        id=node_id,
        type=ntype,
        label=label or node_id,
        known_at=known,
        source="test",
    )


def _edge(subject: str, obj: str, known: date, pred: EdgeType = EdgeType.CLASSIFIED_AS) -> Edge:
    return Edge(subject=subject, predicate=pred, object=obj, known_at=known, source="test")


def _graph(nodes, edges) -> TemporalGraph:
    g = TemporalGraph()
    for n in nodes:
        g.add_node(n)
    for e in edges:
        g.add_edge(e)
    return g


def _simple() -> TemporalGraph:
    return _graph(
        [
            _node(CENTRE, date(2008, 6, 1)),
            _node("hazard:a", date(2010, 6, 1), NodeType.HAZARD),
            _node("product:b", date(2014, 6, 1), NodeType.PRODUCT),
            _node("event:c", date(2019, 6, 1), NodeType.REGULATORY_EVENT),
        ],
        [
            _edge(CENTRE, "hazard:a", date(2010, 6, 1)),
            _edge("product:b", CENTRE, date(2014, 6, 1), EdgeType.CONTAINS),
            _edge(CENTRE, "event:c", date(2019, 6, 1), EdgeType.SUBJECT_OF),
        ],
    )


# ------------------------------------------------------------------ equivalence


def _mesh_graph() -> TemporalGraph:
    """Centre, two shared hazards, and peripheral substances sharing them."""
    nodes = [
        _node(CENTRE, date(2008, 1, 1)),
        _node("hazard:a", date(2010, 6, 1), NodeType.HAZARD),
        _node("hazard:b", date(2010, 6, 1), NodeType.HAZARD),
    ]
    edges = [
        _edge(CENTRE, "hazard:a", date(2010, 6, 1)),
        _edge(CENTRE, "hazard:b", date(2010, 6, 1)),
    ]
    for i in range(6):
        sid = f"substance:cas:{i}-00-0"
        nodes.append(_node(sid, date(2011 + i, 6, 1)))
        edges.append(_edge(sid, "hazard:a", date(2011 + i, 6, 1)))
    return _graph(nodes, edges)


def test_mesh_includes_second_hop_and_creates_cross_links():
    from hazium.graph.timeline import build_evidence_mesh

    mesh = build_evidence_mesh(_mesh_graph(), CENTRE, CUTOFFS)
    ids = {n.id for n in mesh.nodes}

    assert "substance:cas:0-00-0" in ids, "second hop missing"
    # Cross-links are edges that do not touch the centre; they are the whole
    # point of going to two hops.
    cross = [e for e in mesh.edges if CENTRE not in (e.source, e.target)]
    assert len(cross) >= 6


def test_mesh_marks_core_membership():
    from hazium.graph.timeline import build_evidence_mesh

    mesh = build_evidence_mesh(_mesh_graph(), CENTRE, CUTOFFS)
    core = {n.id for n in mesh.nodes if n.core}

    assert core == {CENTRE, "hazard:a", "hazard:b"}


def _reachable_within_two_hops(view, centre: str) -> set[str]:
    """Nodes reachable from ``centre`` in at most two hops, in an as_of view."""
    if not view.has_node(centre):
        return set()
    hop1 = {e.object if e.subject == centre else e.subject for e in view.edges_of(centre)} - {
        centre
    }
    out = {centre} | hop1
    for node_id in hop1:
        out |= {e.object if e.subject == node_id else e.subject for e in view.edges_of(node_id)}
    return out


def test_mesh_frames_match_as_of_reachability():
    # Regression guard. Asserting node EXISTENCE in the as_of view passes even
    # when frames are derived from each node's own known_at, which scatters
    # hundreds of unconnected dots across the early years. Reachability is the
    # property that actually has to hold.
    from hazium.graph.timeline import build_evidence_mesh

    graph = _mesh_graph()
    mesh = build_evidence_mesh(graph, CENTRE, CUTOFFS, max_nodes=1000)
    mesh_ids = {n.id for n in mesh.nodes}

    for frame, cutoff in enumerate(CUTOFFS):
        expected = _reachable_within_two_hops(graph.as_of(cutoff), CENTRE) & mesh_ids
        visible, _ = mesh.visible_at(frame)
        assert visible == expected, f"frame {frame} ({cutoff}) diverges from as_of reachability"


def test_mesh_does_not_show_a_node_before_it_is_connected():
    # A substance that predates everything but only links in later must not
    # appear until the link does.
    from hazium.graph.timeline import build_evidence_mesh

    graph = _graph(
        [
            _node(CENTRE, date(2008, 1, 1)),
            _node("hazard:late", date(2015, 6, 1), NodeType.HAZARD),
            _node("substance:cas:9-00-0", date(1990, 1, 1)),  # ancient, unconnected
        ],
        [
            _edge(CENTRE, "hazard:late", date(2015, 6, 1)),
            _edge("substance:cas:9-00-0", "hazard:late", date(2015, 6, 1)),
        ],
    )
    mesh = build_evidence_mesh(graph, CENTRE, CUTOFFS)
    old = next(n for n in mesh.nodes if n.id == "substance:cas:9-00-0")

    assert CUTOFFS[old.first_frame] == date(2016, 1, 1)
    assert mesh.visible_at(0)[0] == {CENTRE}, "only the centre is knowable in 2009"


def test_mesh_truncation_never_drops_the_core():
    from hazium.graph.timeline import build_evidence_mesh

    mesh = build_evidence_mesh(_mesh_graph(), CENTRE, CUTOFFS, max_nodes=3)
    ids = {n.id for n in mesh.nodes}

    assert ids == {CENTRE, "hazard:a", "hazard:b"}
    assert mesh.truncated == 6
    assert all(e.source in ids and e.target in ids for e in mesh.edges)


def test_mesh_reference_uses_real_identifiers_only():
    from hazium.graph.timeline import build_evidence_mesh

    graph = _graph(
        [
            _node(CENTRE, date(2008, 1, 1)),
            _node("document:10.2903/j.efsa.2013.3066", date(2012, 1, 1), NodeType.DOCUMENT),
            _node("hazard:clp:H302", date(2012, 1, 1), NodeType.HAZARD),
        ],
        [
            _edge(
                CENTRE, "document:10.2903/j.efsa.2013.3066", date(2012, 1, 1), EdgeType.EVIDENCED_BY
            ),
            _edge(CENTRE, "hazard:clp:H302", date(2012, 1, 1)),
        ],
    )
    mesh = build_evidence_mesh(graph, CENTRE, CUTOFFS)
    refs = {n.id: n.ref for n in mesh.nodes}

    assert refs["document:10.2903/j.efsa.2013.3066"] == "doi:10.2903/j.efsa.2013.3066"
    # No invented identifier for a hazard code, nor for a substance id that
    # carries no CAS: the client shows no link rather than a guessed one.
    assert refs["hazard:clp:H302"] == ""
    assert refs[CENTRE] == ""


def test_mesh_reference_extracts_cas_when_present():
    from hazium.graph.timeline import build_evidence_mesh

    cas_id = "substance:cas:210880-92-5"
    graph = _graph(
        [_node(cas_id, date(2008, 1, 1)), _node("hazard:x", date(2010, 1, 1), NodeType.HAZARD)],
        [_edge(cas_id, "hazard:x", date(2010, 1, 1))],
    )
    mesh = build_evidence_mesh(graph, cas_id, CUTOFFS)
    refs = {n.id: n.ref for n in mesh.nodes}

    assert refs[cas_id] == "cas:210880-92-5"


def test_mesh_deduplicates_parallel_edges():
    from hazium.graph.timeline import build_evidence_mesh

    graph = _graph(
        [_node(CENTRE, date(2008, 1, 1)), _node("hazard:d", date(2010, 1, 1), NodeType.HAZARD)],
        [
            _edge(CENTRE, "hazard:d", date(2010, 1, 1)),
            _edge(CENTRE, "hazard:d", date(2010, 1, 1)),
        ],
    )
    mesh = build_evidence_mesh(graph, CENTRE, CUTOFFS)
    assert len(mesh.edges) == 1


def test_node_reachable_both_directly_and_via_two_hops_uses_the_earlier_route():
    # Regression guard, from real data: thiamethoxam is a direct neighbour of
    # clothianidin via a degrades_to edge that only becomes knowable in 2013,
    # AND a second-hop neighbour via three shared hazard classifications known
    # in 2011. It is reachable within two hops from 2011, so it must appear
    # then, not two years later.
    from hazium.graph.timeline import build_evidence_mesh

    graph = _graph(
        [
            _node(CENTRE, date(2008, 1, 1)),
            _node("hazard:shared", date(2010, 6, 1), NodeType.HAZARD),
            _node("substance:cas:2-00-0", date(2007, 1, 1)),
        ],
        [
            _edge(CENTRE, "hazard:shared", date(2010, 6, 1)),
            _edge("substance:cas:2-00-0", "hazard:shared", date(2010, 6, 1)),
            # Direct link, but knowable years later.
            _edge("substance:cas:2-00-0", CENTRE, date(2016, 6, 1), EdgeType.DEGRADES_TO),
        ],
    )
    mesh = build_evidence_mesh(graph, CENTRE, CUTOFFS, max_nodes=1000)
    node = next(n for n in mesh.nodes if n.id == "substance:cas:2-00-0")

    assert CUTOFFS[node.first_frame] == date(2011, 1, 1), "must use the early two-hop route"
    assert node.core, "still a direct neighbour"


def test_mesh_edge_never_precedes_either_endpoint():
    # Node frames are reachability-based and can be later than the edge's own
    # knowability, so without a clamp a frame reports links between nodes that
    # are not on screen. Caught in the browser as "2 facts, 10 links".
    from hazium.graph.timeline import build_evidence_mesh

    mesh = build_evidence_mesh(_mesh_graph(), CENTRE, CUTOFFS, max_nodes=1000)
    frame_of = {n.id: n.first_frame for n in mesh.nodes}

    for e in mesh.edges:
        assert e.first_frame >= frame_of[e.source]
        assert e.first_frame >= frame_of[e.target]


def test_mesh_link_count_is_zero_while_only_the_centre_is_visible():
    from hazium.graph.timeline import build_evidence_mesh

    mesh = build_evidence_mesh(_mesh_graph(), CENTRE, CUTOFFS, max_nodes=1000)
    nodes, edges = mesh.visible_at(0)

    assert nodes == {CENTRE}
    assert edges == 0


def test_mesh_via_explains_a_shared_attribute_route():
    # Without this a reader cannot tell a metabolite from one of the hundreds of
    # substances that merely carry the same hazard code. On the real graph 557 of
    # 597 nodes are shared-hazard cohort members, not relatives.
    from hazium.graph.timeline import build_evidence_mesh

    mesh = build_evidence_mesh(_mesh_graph(), CENTRE, CUTOFFS, max_nodes=1000)
    peripheral = next(n for n in mesh.nodes if n.id == "substance:cas:0-00-0")

    assert peripheral.via == "shared:hazard:a"
    assert not peripheral.core


def test_mesh_via_reports_the_direct_relationship_for_core_nodes():
    # A direct relationship is the more informative explanation and must survive
    # even when a shared-attribute route is what made the node visible earlier:
    # thiamethoxam appears via a shared hazard code but degrades_to is the fact
    # that matters.
    from hazium.graph.timeline import build_evidence_mesh

    graph = _graph(
        [
            _node(CENTRE, date(2008, 1, 1)),
            _node("hazard:shared", date(2010, 6, 1), NodeType.HAZARD),
            _node("substance:cas:2-00-0", date(2007, 1, 1)),
        ],
        [
            _edge(CENTRE, "hazard:shared", date(2010, 6, 1)),
            _edge("substance:cas:2-00-0", "hazard:shared", date(2010, 6, 1)),
            _edge("substance:cas:2-00-0", CENTRE, date(2016, 6, 1), EdgeType.DEGRADES_TO),
        ],
    )
    mesh = build_evidence_mesh(graph, CENTRE, CUTOFFS, max_nodes=1000)
    node = next(n for n in mesh.nodes if n.id == "substance:cas:2-00-0")

    assert node.via == "direct:degrades_to"
    assert CUTOFFS[node.first_frame] == date(2011, 1, 1), "still surfaces via the early route"


# ------------------------------------------------------------------- validation


def test_mesh_unknown_centre_raises():
    from hazium.graph.timeline import build_evidence_mesh

    with pytest.raises(KeyError, match="unknown node"):
        build_evidence_mesh(_mesh_graph(), "substance:nope", CUTOFFS)


def test_mesh_empty_cutoffs_raise():
    from hazium.graph.timeline import build_evidence_mesh

    with pytest.raises(ValueError, match="must not be empty"):
        build_evidence_mesh(_mesh_graph(), CENTRE, [])


def test_mesh_unordered_cutoffs_raise():
    from hazium.graph.timeline import build_evidence_mesh

    with pytest.raises(ValueError, match="strictly ascending"):
        build_evidence_mesh(_mesh_graph(), CENTRE, [date(2020, 1, 1), date(2010, 1, 1)])


def test_mesh_duplicate_cutoffs_raise():
    from hazium.graph.timeline import build_evidence_mesh

    with pytest.raises(ValueError, match="strictly ascending"):
        build_evidence_mesh(_mesh_graph(), CENTRE, [date(2020, 1, 1), date(2020, 1, 1)])


def test_mesh_centre_unknowable_in_range_is_empty():
    from hazium.graph.timeline import build_evidence_mesh

    graph = _graph([_node(CENTRE, date(2030, 1, 1))], [])
    mesh = build_evidence_mesh(graph, CENTRE, CUTOFFS)

    assert mesh.nodes == ()
    assert mesh.edges == ()
