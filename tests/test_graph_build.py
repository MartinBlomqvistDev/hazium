"""Building the register structure graph, on a fluazinam-shaped fixture."""

from datetime import date

from hazium.graph.build import build_from_register
from hazium.models import (
    EdgeType,
    NodeType,
    ProductIngredient,
    ProductRegistration,
    Substance,
)

SNAPSHOT = date(2026, 7, 3)


def _substance(name: str, cas: str | None) -> Substance:
    return Substance(name=name, cas_number=cas, source="kemi:bkmreg", known_at=SNAPSHOT)


def _product(
    reg: str,
    name: str,
    ingredients: list[ProductIngredient],
    approved: bool,
    object_type: int = 1,
) -> ProductRegistration:
    return ProductRegistration(
        registration_number=reg,
        product_name_id=int(reg),
        object_type=object_type,
        name=name,
        country="SE",
        main_group="Växtskyddsmedel",
        approved=approved,
        previously_approved=False,
        usage_ban=False,
        ingredients=tuple(ingredients),
        source="kemi:bkmreg",
        known_at=SNAPSHOT,
    )


FLUAZINAM = ProductIngredient(name="Fluazinam", cas_number="79622-59-6", concentration="500 g/L")


def _fixture_graph():
    return build_from_register(
        substances=[_substance("Fluazinam", "79622-59-6")],
        products=[_product("3957", "Shirlan", [FLUAZINAM], approved=True)],
    )


def test_substance_and_product_nodes_exist() -> None:
    graph = _fixture_graph()
    assert graph.node("substance:cas:79622-59-6").type == NodeType.SUBSTANCE
    assert graph.node("product:se:3957").label == "Shirlan"


def test_contains_edge_links_product_to_substance() -> None:
    graph = _fixture_graph()
    edges = graph.edges_of("product:se:3957")
    contains = [e for e in edges if e.predicate == EdgeType.CONTAINS]
    assert len(contains) == 1
    assert contains[0].object == "substance:cas:79622-59-6"


def test_fluazinam_traverses_to_sweden_via_approval() -> None:
    graph = _fixture_graph()
    paths = graph.evidence_paths("substance:cas:79622-59-6", "country:SE")
    assert any([e.predicate for e in p] == [EdgeType.APPROVED_IN] for p in paths)


def test_ingredient_absent_from_substance_list_is_added_explicitly() -> None:
    # product declares a substance the register substance list omitted
    graph = build_from_register(
        substances=[],
        products=[_product("1", "X", [FLUAZINAM], approved=True)],
    )
    assert graph.has_node("substance:cas:79622-59-6")


def test_approval_edge_only_for_approved_products() -> None:
    graph = build_from_register(
        substances=[_substance("Fluazinam", "79622-59-6")],
        products=[_product("9", "Old", [FLUAZINAM], approved=False)],
    )
    assert graph.evidence_paths("substance:cas:79622-59-6", "country:SE") == []


def test_approval_edge_deduplicated_across_products() -> None:
    graph = build_from_register(
        substances=[_substance("Fluazinam", "79622-59-6")],
        products=[
            _product("1", "A", [FLUAZINAM], approved=True),
            _product("2", "B", [FLUAZINAM], approved=True),
        ],
    )
    approved = [e for e in graph.edges() if e.predicate == EdgeType.APPROVED_IN]
    assert len(approved) == 1


def test_regulatory_sub_objects_are_not_product_nodes() -> None:
    # object_type 4 is an additional-name row, not an actual product
    graph = build_from_register(
        substances=[_substance("Fluazinam", "79622-59-6")],
        products=[_product("42", "Parallel import", [FLUAZINAM], approved=True, object_type=4)],
    )
    assert not graph.has_node("product:se:42")
    assert graph.evidence_paths("substance:cas:79622-59-6", "country:SE") == []


def test_register_structure_absent_before_snapshot() -> None:
    graph = _fixture_graph()
    assert len(graph.as_of(date(2023, 1, 1))) == 0
