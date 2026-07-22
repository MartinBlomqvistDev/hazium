"""Evidence timelines: a substance's neighbourhood, revealed as it became knowable.

This is the temporal-integrity claim made visible. A static knowledge graph shows
what is true now; this shows what was *knowable* at each cutoff, which is the only
thing a retrodetection claim may rest on. Each node and edge carries the frame at
which it enters the view, so a client can replay evidence accumulating around a
substance in the years before its regulatory action.

The output is deliberately a single reveal-ordered structure rather than one
subgraph per cutoff. Consecutive cutoffs overlap almost entirely, so per-frame
snapshots would repeat the same elements sixteen times; a ``first_frame`` index
carries identical information and stays small enough to commit alongside the site.

Frame semantics follow ``TemporalGraph.as_of`` exactly, and
``test_timeline_matches_as_of_at_every_cutoff`` asserts that equivalence rather
than trusting this docstring:

* a node enters at the first cutoff strictly greater than its ``known_at``;
* an edge additionally waits for both endpoints, because ``as_of`` drops an edge
  whose endpoints are not yet in view.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from hazium.graph.store import TemporalGraph


class TimelineEdge(BaseModel):
    """An edge in an evidence timeline."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str
    target: str
    predicate: str
    first_frame: int


class MeshNode(BaseModel):
    """A node in a two-hop evidence mesh."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    label: str
    type: str
    first_frame: int
    core: bool = Field(description="Direct neighbour of the centre, or the centre itself")
    ref: str = Field(default="", description="Identifier for linking, e.g. 'doi:...' or 'cas:...'")
    via: str = Field(
        default="",
        description=(
            "Why this node is in the mesh. 'direct:<predicate>' for a neighbour of "
            "the centre, 'shared:<label>' for a node reached through a shared "
            "attribute. Without it a reader cannot tell a metabolite from one of "
            "the hundreds of substances that merely carry the same hazard code."
        ),
    )


class EvidenceMesh(BaseModel):
    """A substance's two-hop neighbourhood, ordered by when each part became knowable.

    The one-hop timeline is a star: everything connects to the centre and
    nothing to anything else, which is structurally sparse however it is drawn.
    Two hops brings in the substances that share a hazard classification or an
    assessment, and those cross-links are what make the picture a network. They
    are also meaningful rather than decorative: shared-hazard structure is
    already a model feature (``graph_shared_hazard_substance_count``).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    center: str
    center_label: str
    cutoffs: tuple[str, ...]
    nodes: tuple[MeshNode, ...]
    edges: tuple[TimelineEdge, ...]
    truncated: int = 0

    def visible_at(self, frame: int) -> tuple[set[str], int]:
        """Node ids and edge count visible at ``frame``."""
        ids = {n.id for n in self.nodes if n.first_frame <= frame}
        return ids, sum(1 for e in self.edges if e.first_frame <= frame)


def _reference(node_id: str, node_type: str, attrs: dict) -> str:
    """A stable external identifier for a node, or an empty string.

    Derived from the node id, which already encodes the identifier the source
    used: EFSA documents are keyed by DOI and substances by CAS. Nothing is
    invented here; a node with no usable identifier gets no reference, and the
    client shows no link rather than a guessed one.
    """
    if node_type == "document" and node_id.startswith("document:"):
        return "doi:" + node_id.removeprefix("document:")
    if node_type == "substance" and ":cas:" in node_id:
        return "cas:" + node_id.split(":cas:", 1)[1]
    if node_type == "regulatory_event" and attrs.get("kind"):
        return "kind:" + str(attrs["kind"])
    return ""


def build_evidence_mesh(
    graph: TemporalGraph,
    center_id: str,
    cutoffs: Sequence[date],
    *,
    max_nodes: int = 800,
) -> EvidenceMesh:
    """Build the reveal-ordered two-hop neighbourhood of ``center_id``.

    Frames follow ``as_of`` exactly: a node
    enters at the first cutoff strictly after its ``known_at``, and an edge
    additionally waits for both endpoints.

    Args:
        graph: The full graph. Not mutated.
        center_id: Node the mesh is centred on.
        cutoffs: Ascending cutoff dates.
        max_nodes: Cap on total nodes. Second-hop nodes are dropped first,
            earliest-appearing kept, so truncation is deterministic and never
            removes the core.

    Returns:
        The mesh.

    Raises:
        KeyError: If ``center_id`` is unknown.
        ValueError: If ``cutoffs`` is empty or not strictly ascending.
    """
    if not graph.has_node(center_id):
        raise KeyError(f"unknown node: {center_id!r}")
    if not cutoffs:
        raise ValueError("cutoffs must not be empty")
    if any(b <= a for a, b in zip(cutoffs, cutoffs[1:], strict=False)):
        raise ValueError("cutoffs must be strictly ascending")

    centre = graph.node(center_id)
    centre_frame = _first_frame(centre.known_at, cutoffs)
    if centre_frame is None:
        return EvidenceMesh(
            center=center_id,
            center_label=centre.label,
            cutoffs=tuple(c.isoformat() for c in cutoffs),
            nodes=(),
            edges=(),
        )

    def edge_frame(edge) -> int | None:
        """Frame at which an edge and both its endpoints are all knowable."""
        latest = max(
            edge.known_at,
            graph.node(edge.subject).known_at,
            graph.node(edge.object).known_at,
        )
        return _first_frame(latest, cutoffs)

    # A node appears when it becomes CONNECTED to the centre, not merely when it
    # exists. Assigning frames from each node's own known_at would scatter
    # hundreds of unattached dots across the early years: substances that
    # predate the centre's hazard classification but are not yet linked to
    # anything. The mesh must show reachability, which is what as_of shows.
    # Two distinct quantities, and conflating them is a trap in both directions.
    #
    #   direct_frame  when a node becomes a DIRECT neighbour of the centre.
    #                 Only this may serve as the base for a second hop, because
    #                 expanding from a node that is itself two hops away reaches
    #                 nodes three hops out.
    #   node_frame    when a node becomes VISIBLE, minimised over every route of
    #                 at most two hops. This is what the renderer uses.
    #
    # Thiamethoxam needs both: it reaches clothianidin through three shared
    # hazard classifications in 2011, while its direct degrades_to edge is only
    # knowable from 2013. It must appear in 2011, yet must not act as a stepping
    # stone until 2013.
    direct_frame: dict[str, int] = {}
    via: dict[str, str] = {}
    core = {center_id}
    for edge in graph.edges_of(center_id):
        other = edge.object if edge.subject == center_id else edge.subject
        if other == center_id:
            continue
        frame = edge_frame(edge)
        if frame is None:
            continue
        frame = max(frame, centre_frame)
        core.add(other)
        if other not in direct_frame or frame < direct_frame[other]:
            direct_frame[other] = frame
            via[other] = f"direct:{edge.predicate.value}"

    node_frame: dict[str, int] = {center_id: centre_frame, **direct_frame}

    for node_id in sorted(direct_frame):
        via_base = direct_frame[node_id]
        for edge in graph.edges_of(node_id):
            other = edge.object if edge.subject == node_id else edge.subject
            if other == node_id or other == center_id:
                continue
            frame = edge_frame(edge)
            if frame is None:
                continue
            frame = max(frame, via_base)
            if other not in node_frame or frame < node_frame[other]:
                node_frame[other] = frame
                # A direct relationship is the more informative explanation, so
                # it is never overwritten by a shared-attribute route even when
                # that route is what made the node visible earlier. Thiamethoxam
                # appears in 2011 through a shared hazard code, but what a reader
                # needs to know is that it degrades into the focal substance.
                if other not in core:
                    via[other] = f"shared:{graph.node(node_id).label}"

    edge_rows: list[tuple[int, str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for edge in graph.edges():
        if edge.subject == edge.object:
            continue
        if edge.subject not in node_frame or edge.object not in node_frame:
            continue
        key = (edge.subject, edge.predicate.value, edge.object)
        if key in seen:
            continue
        latest = max(
            edge.known_at, graph.node(edge.subject).known_at, graph.node(edge.object).known_at
        )
        frame = _first_frame(latest, cutoffs)
        if frame is None:
            continue
        # An edge cannot appear before either endpoint is visible. Node frames
        # are reachability-based and can therefore be later than the raw
        # knowability of the edge, so this clamp is what keeps the two
        # consistent; without it a frame can report links between nodes that are
        # not on screen yet.
        frame = max(frame, node_frame[edge.subject], node_frame[edge.object])
        seen.add(key)
        edge_rows.append((frame, edge.subject, edge.object, edge.predicate.value))

    # Keep the core whatever happens; drop the furthest, latest periphery first.
    ranked = sorted(node_frame.items(), key=lambda kv: (kv[0] not in core, kv[1], kv[0]))
    kept_ids = {node_id for node_id, _ in ranked[:max_nodes]}
    truncated = max(0, len(ranked) - max_nodes)

    nodes = tuple(
        MeshNode(
            id=node_id,
            label=graph.node(node_id).label,
            type=graph.node(node_id).type.value,
            first_frame=frame,
            core=node_id in core,
            ref=_reference(node_id, graph.node(node_id).type.value, graph.node(node_id).attrs),
            via=via.get(node_id, ""),
        )
        for node_id, frame in ranked[:max_nodes]
    )
    edges = tuple(
        TimelineEdge(source=s, target=o, predicate=p, first_frame=f)
        for f, s, o, p in sorted(edge_rows)
        if s in kept_ids and o in kept_ids
    )
    return EvidenceMesh(
        center=center_id,
        center_label=centre.label,
        cutoffs=tuple(c.isoformat() for c in cutoffs),
        nodes=nodes,
        edges=edges,
        truncated=truncated,
    )


def _first_frame(known_at: date, cutoffs: Sequence[date]) -> int | None:
    """Index of the first cutoff strictly greater than ``known_at``.

    ``as_of`` admits a fact when ``known_at < cutoff``, so a fact known on the
    cutoff date itself belongs to the next frame, not this one.
    """
    for i, cutoff in enumerate(cutoffs):
        if known_at < cutoff:
            return i
    return None
