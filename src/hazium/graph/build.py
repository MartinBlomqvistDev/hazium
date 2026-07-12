"""Assemble and extend the temporal graph from ingested facts.

``build_from_register`` builds the regulatory-commercial substructure: which
products contain which substances, and which substances are approved for use
in Sweden. It is deliberately the *structure* layer, not the
*evidence-over-time* layer:

* Product containment is a raw register fact: ``product -CONTAINS-> substance``.
* Approval is derived and substance-level, matching the north-star question
  ("substances approved in Sweden"): ``substance -APPROVED_IN-> country`` is
  emitted for any substance in at least one currently-approved product.

Temporal caveat: the register is a live snapshot with no history, so every
node and edge from it carries ``known_at`` = the snapshot date. An ``as_of``
view before that date is therefore empty of register structure. Retrodetection
rests on sources that carry real dates (sales reports, EFSA conclusions).

``merge_openfoodtox`` layers EFSA structure onto an existing graph: dated
scientific evidence and degradation edges. Because both use the same
CAS-priority node id scheme, EFSA identity naturally lands on the same nodes
KEMI already created (e.g. fluazinam), rather than creating parallel ones.

``merge_clp`` layers ECHA Annex VI hazard classifications the same way, but
scoped to substances the graph already knows about (see its docstring).
``merge_eu_ppdb`` layers EU regulatory events (approvals, non-renewals) with
the same scoping; its non-renewal events are V1's regulatory-action label.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from hazium.graph.store import TemporalGraph
from hazium.models import (
    AttrValue,
    DegradationLink,
    Edge,
    EdgeType,
    HazardClassification,
    Node,
    NodeType,
    ProductRegistration,
    RegulatoryEvent,
    SourceDocument,
    Substance,
)
from hazium.resolve.ids import (
    country_node_id,
    document_node_id,
    hazard_node_id,
    product_node_id,
    regulatory_event_node_id,
    safe_substance_node_id,
    substance_node_id,
)

# Register objektTypId for a marketed product, as opposed to an additional
# name, dispensation, or parallel-trade permit.
ACTUAL_PRODUCT = 1


def build_from_register(
    substances: list[Substance],
    products: list[ProductRegistration],
) -> TemporalGraph:
    """Build the register structure graph.

    The product layer is scoped to actual products (``object_type == 1``),
    excluding regulatory sub-objects (additional names, dispensations,
    parallel-trade permits) that would double-count or collapse ambiguously.
    Substance nodes come from the register's substance list; any ingredient
    naming a substance absent from that list is added explicitly, so edges
    never create nodes implicitly. Approval edges are deduplicated to one per
    (substance, country).
    """
    graph = TemporalGraph()

    for substance in substances:
        graph.add_node(_substance_node(substance))

    products = [p for p in products if p.object_type == ACTUAL_PRODUCT]
    # The register is a single snapshot; derivations share its known_at.
    snapshot = min(product.known_at for product in products) if products else date.today()

    approved_substances: set[tuple[str, str]] = set()
    for product in products:
        product_id = product_node_id(product.country, product.product_name_id)
        graph.add_node(
            Node(
                id=product_id,
                type=NodeType.PRODUCT,
                label=product.name,
                source=product.source,
                known_at=product.known_at,
            )
        )
        for ingredient in product.ingredients:
            substance_id = substance_node_id(
                cas_number=ingredient.cas_number,
                name=ingredient.name,
            )
            if not graph.has_node(substance_id):
                graph.add_node(
                    Node(
                        id=substance_id,
                        type=NodeType.SUBSTANCE,
                        label=ingredient.name,
                        source=product.source,
                        known_at=product.known_at,
                    )
                )
            graph.add_edge(
                Edge(
                    subject=product_id,
                    predicate=EdgeType.CONTAINS,
                    object=substance_id,
                    source=product.source,
                    known_at=product.known_at,
                )
            )
            if product.approved:
                approved_substances.add((substance_id, product.country))

    for substance_id, country in sorted(approved_substances):
        country_id = country_node_id(country)
        if not graph.has_node(country_id):
            graph.add_node(
                Node(
                    id=country_id,
                    type=NodeType.COUNTRY,
                    label=country,
                    source="hazium:derived",
                    known_at=snapshot,
                )
            )
        graph.add_edge(
            Edge(
                subject=substance_id,
                predicate=EdgeType.APPROVED_IN,
                object=country_id,
                source="kemi:bkmreg",
                known_at=snapshot,
            )
        )

    return graph


def _substance_node(substance: Substance) -> Node:
    # safe_substance_node_id, not the strict version: a Substance record
    # already accepted at ingestion (e.g. from OpenFoodTox, which tolerates
    # a small fraction of malformed source CAS values) must remain buildable.
    return Node(
        id=safe_substance_node_id(cas_number=substance.cas_number, name=substance.name),
        type=NodeType.SUBSTANCE,
        label=substance.name,
        source=substance.source,
        known_at=substance.known_at,
    )


def _pull_known_at_earlier(graph: TemporalGraph, node_id: str, source: str, known_at: date) -> None:
    """Let a dated fact about an existing node pull the node's own ``known_at``
    earlier, via ``add_node``'s keep-earliest semantics.

    A node's ``known_at`` is "the earliest date this entity was publicly
    knowable to Hazium", not just the date of whichever ingestion snapshot
    happened to create the node first. Without this, a substance created only
    from a live register/export snapshot (e.g. fluazinam's node getting its
    ``known_at`` from OpenFoodTox's 2026 publication date) would never appear
    in an ``as_of`` view before that snapshot date, even when the graph holds
    genuinely dated evidence about it from years earlier (an EFSA conclusion,
    a CLP classification). That would silently defeat the whole point of
    ingesting dated evidence: the north-star retrodetection question requires
    the substance itself, not just its edges, to survive the cutoff.
    """
    existing = graph.node(node_id)
    if known_at < existing.known_at:
        graph.add_node(
            Node(
                id=existing.id,
                type=existing.type,
                label=existing.label,
                source=source,
                known_at=known_at,
            )
        )


def merge_openfoodtox(
    graph: TemporalGraph,
    substances: list[Substance],
    degradation_links: list[DegradationLink],
    documents: list[SourceDocument],
) -> None:
    """Layer EFSA OpenFoodTox structure onto an existing graph, in place.

    Substance nodes are added first so every degradation and evidence edge
    has both endpoints available; ``DegradationLink`` and ``SourceDocument``
    already carry resolved substance ids (the adapter's job, not this
    builder's), matching how ``SalesRecord``/``HazardClassification`` work.
    """
    for substance in substances:
        graph.add_node(_substance_node(substance))

    for link in degradation_links:
        graph.add_edge(
            Edge(
                subject=link.parent_substance_id,
                predicate=EdgeType.DEGRADES_TO,
                object=link.metabolite_substance_id,
                source=link.source,
                known_at=link.known_at,
            )
        )

    for document in documents:
        doc_id = document_node_id(document.id)
        graph.add_node(
            Node(
                id=doc_id,
                type=NodeType.DOCUMENT,
                label=document.title,
                source=document.source,
                known_at=document.known_at,
            )
        )
        if document.subject_substance_id:
            # No has_node guard: subject_substance_id is either unset or
            # resolved from the same index as `substances`, so the endpoint
            # must exist. A missing node here is a real ingestion bug and
            # should raise (TemporalGraph.add_edge), not be swallowed.
            _pull_known_at_earlier(
                graph, document.subject_substance_id, document.source, document.known_at
            )
            graph.add_edge(
                Edge(
                    subject=document.subject_substance_id,
                    predicate=EdgeType.EVIDENCED_BY,
                    object=doc_id,
                    source=document.source,
                    known_at=document.known_at,
                )
            )


def merge_clp(graph: TemporalGraph, classifications: list[HazardClassification]) -> tuple[int, int]:
    """Layer ECHA Annex VI hazard classifications onto an existing graph.

    Scoped to substances already present in the graph: Annex VI covers
    ~4,400 substances across the whole of EU chemicals regulation, the
    overwhelming majority outside the pesticide domain V0 targets, so
    classifications for substances not yet in the graph (from KEMI or
    OpenFoodTox) are skipped rather than conjuring thousands of unrelated
    industrial-chemical nodes. Returns ``(applied, skipped)`` for the
    pipeline to report.

    No dedup on repeat (substance, hazard) pairs across ATPs: each row is a
    distinct dated fact (a reclassification), matching the "corrections are
    new facts, never mutations" rule -- multiple ``CLASSIFIED_AS`` edges for
    the same pair, at different ``known_at``, is the correct representation
    of a substance being reclassified over time.
    """
    applied = skipped = 0
    for classification in classifications:
        if not graph.has_node(classification.substance_id):
            skipped += 1
            continue
        _pull_known_at_earlier(
            graph, classification.substance_id, classification.source, classification.known_at
        )
        hazard_id = hazard_node_id(classification.hazard_code)
        if not graph.has_node(hazard_id):
            graph.add_node(
                Node(
                    id=hazard_id,
                    type=NodeType.HAZARD,
                    label=classification.hazard_code,
                    source=classification.source,
                    known_at=classification.known_at,
                )
            )
        attrs: dict[str, AttrValue] = {}
        if classification.hazard_class:
            attrs["hazard_class"] = classification.hazard_class
        if classification.atp:
            attrs["atp"] = classification.atp
        if classification.celex:
            attrs["celex"] = classification.celex
        graph.add_edge(
            Edge(
                subject=classification.substance_id,
                predicate=EdgeType.CLASSIFIED_AS,
                object=hazard_id,
                source=classification.source,
                known_at=classification.known_at,
                attrs=attrs,
            )
        )
        applied += 1
    return applied, skipped


def merge_eu_ppdb(graph: TemporalGraph, events: list[RegulatoryEvent]) -> tuple[int, int]:
    """Layer EU regulatory events onto an existing graph, in place.

    Scoped to substances already present (like ``merge_clp``): the EU register
    covers thousands of substances, most outside the pesticide domain the graph
    holds, so an event whose substance is absent is counted and skipped.
    Returns ``(applied, skipped)``.

    Each event becomes a ``regulatory_event`` node plus a ``SUBJECT_OF`` edge
    from the substance. A dated event also pulls the substance node's own
    ``known_at`` earlier (an approval dated 2009 is proof the substance was
    knowable in 2009): the same fix `merge_openfoodtox`/`merge_clp` rely on for
    the substance to survive an early ``as_of`` view, not just its edges.
    """
    applied = skipped = 0
    for event in events:
        if not graph.has_node(event.substance_id):
            skipped += 1
            continue
        _pull_known_at_earlier(graph, event.substance_id, event.source, event.known_at)
        event_id = regulatory_event_node_id(
            event.substance_id, event.kind.value, event.event_date.isoformat()
        )
        graph.add_node(
            Node(
                id=event_id,
                type=NodeType.REGULATORY_EVENT,
                label=f"{event.kind.value} {event.event_date.isoformat()}",
                source=event.source,
                known_at=event.known_at,
                attrs={"kind": event.kind.value, "jurisdiction": event.jurisdiction},
            )
        )
        graph.add_edge(
            Edge(
                subject=event.substance_id,
                predicate=EdgeType.SUBJECT_OF,
                object=event_id,
                source=event.source,
                known_at=event.known_at,
            )
        )
        applied += 1
    return applied, skipped


def load_graph(nodes_path: Path, edges_path: Path) -> TemporalGraph:
    """Reconstruct a graph previously serialized by a pipeline step."""
    graph = TemporalGraph()
    with nodes_path.open(encoding="utf-8") as f:
        for line in f:
            graph.add_node(Node.model_validate_json(line))
    with edges_path.open(encoding="utf-8") as f:
        for line in f:
            graph.add_edge(Edge.model_validate_json(line))
    return graph
