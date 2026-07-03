"""Assemble a temporal graph from KEMI register facts.

This builds the regulatory-commercial substructure of the knowledge graph:
which products contain which substances, and which substances are approved
for use in Sweden. It is deliberately the *structure* layer, not the
*evidence-over-time* layer:

* Product containment is a raw register fact: ``product -CONTAINS-> substance``.
* Approval is derived and substance-level, matching the north-star question
  ("substances approved in Sweden"): ``substance -APPROVED_IN-> country`` is
  emitted for any substance in at least one currently-approved product.

Temporal caveat: the register is a live snapshot with no history, so every
node and edge here carries ``known_at`` = the snapshot date. An ``as_of``
view before that date is therefore empty of register structure. Retrodetection
rests on sources that carry real dates (sales reports, EFSA conclusions), not
on this layer; degradation edges (fluazinam -> TFA) come from those sources
too, not from KEMI.
"""

from __future__ import annotations

from datetime import date

from hazium.graph.store import TemporalGraph
from hazium.models import (
    Edge,
    EdgeType,
    Node,
    NodeType,
    ProductRegistration,
    Substance,
)
from hazium.resolve.ids import country_node_id, product_node_id, substance_node_id

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
    return Node(
        id=substance_node_id(cas_number=substance.cas_number, name=substance.name),
        type=NodeType.SUBSTANCE,
        label=substance.name,
        source=substance.source,
        known_at=substance.known_at,
    )
