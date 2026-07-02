"""In-memory temporal knowledge graph.

Reference implementation of Hazium's temporal semantics: the view
``as_of(cutoff)`` contains exactly the facts with ``known_at`` strictly
before the cutoff. Every retrospective evaluation must run on such a view.

Postgres becomes the source of truth once ingestion lands; this store is
the query surface and the semantics contract that any backend must satisfy.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from datetime import date

from hazium.models import Edge, Node


class TemporalGraph:
    """A directed multigraph of temporally-anchored, source-attributed facts."""

    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._edges: list[Edge] = []
        self._out: dict[str, list[Edge]] = defaultdict(list)
        self._in: dict[str, list[Edge]] = defaultdict(list)

    def __len__(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    def add_node(self, node: Node) -> None:
        """Register a node, keeping the earliest-known version on conflict."""
        existing = self._nodes.get(node.id)
        if existing is None or node.known_at < existing.known_at:
            self._nodes[node.id] = node

    def add_edge(self, edge: Edge) -> None:
        """Register an edge between existing nodes.

        Raises:
            KeyError: If either endpoint is unknown. Edges never create
                nodes implicitly; identity is the resolve module's job.
        """
        for endpoint in (edge.subject, edge.object):
            if endpoint not in self._nodes:
                raise KeyError(f"unknown node: {endpoint!r}")
        self._edges.append(edge)
        self._out[edge.subject].append(edge)
        self._in[edge.object].append(edge)

    def node(self, node_id: str) -> Node:
        return self._nodes[node_id]

    def edges_of(self, node_id: str) -> list[Edge]:
        """All edges incident to a node, in either direction."""
        return [*self._out.get(node_id, []), *self._in.get(node_id, [])]

    def as_of(self, cutoff: date) -> TemporalGraph:
        """The graph as it was publicly knowable strictly before ``cutoff``.

        This is the only legitimate input to a retrospective evaluation.
        """
        view = TemporalGraph()
        for node in self._nodes.values():
            if node.known_at < cutoff:
                view.add_node(node)
        for edge in self._edges:
            if (
                edge.known_at < cutoff
                and edge.subject in view._nodes
                and edge.object in view._nodes
            ):
                view.add_edge(edge)
        return view

    def evidence_paths(self, start: str, end: str, max_depth: int = 4) -> list[list[Edge]]:
        """All simple paths between two nodes, traversed undirected.

        Evidence is about connection, not direction: a crop is connected to
        a substance through a product regardless of edge orientation. Paths
        are capped at ``max_depth`` edges.
        """
        if start not in self._nodes or end not in self._nodes:
            return []
        paths: list[list[Edge]] = []
        self._walk(start, end, {start}, [], max_depth, paths)
        return paths

    def _walk(
        self,
        current: str,
        end: str,
        visited: set[str],
        trail: list[Edge],
        max_depth: int,
        paths: list[list[Edge]],
    ) -> None:
        if len(trail) >= max_depth:
            return
        for edge, neighbor in self._incident(current):
            if neighbor in visited:
                continue
            if neighbor == end:
                paths.append([*trail, edge])
                continue
            self._walk(neighbor, end, visited | {neighbor}, [*trail, edge], max_depth, paths)

    def _incident(self, node_id: str) -> Iterator[tuple[Edge, str]]:
        for edge in self._out.get(node_id, []):
            yield edge, edge.object
        for edge in self._in.get(node_id, []):
            yield edge, edge.subject
