"""Build the register structure graph and verify the fluazinam north-star.

Loads the ingested register facts, builds the graph, joins the sales
substances onto it via the resolver (reporting coverage), runs the fluazinam
reconstruction as a live check, and serializes nodes and edges to JSONL.

Usage:
    python pipeline/03_build_graph.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pydantic import BaseModel

from hazium.graph.build import build_from_register
from hazium.graph.store import TemporalGraph
from hazium.models import EdgeType, ProductRegistration, SalesRecord, Substance
from hazium.resolve.names import SubstanceResolver

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"

FLUAZINAM_ID = "substance:cas:79622-59-6"
SWEDEN_ID = "country:SE"


def _load(path: Path, model: type[BaseModel]) -> list:
    with path.open(encoding="utf-8") as f:
        return [model.model_validate_json(line) for line in f]


def _write_jsonl(path: Path, records: list[BaseModel]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(record.model_dump_json() + "\n")


def _report_sales_coverage(resolver: SubstanceResolver, sales: list[SalesRecord]) -> None:
    """How much of the sales signal reaches an identified graph substance."""
    latest: dict[str, SalesRecord] = {}
    for record in sales:
        key = record.substance_id
        if key not in latest or record.year > latest[key].year:
            latest[key] = record

    matched = matched_tonnes = total_tonnes = 0
    for record in latest.values():
        name = record.substance_id.removeprefix("substance:name:").replace("-", " ")
        total_tonnes += record.tonnes_active_substance
        if resolver.resolve(name).matched:
            matched += 1
            matched_tonnes += record.tonnes_active_substance

    n = len(latest)
    print(
        f"sales substances resolved to register: {matched}/{n} "
        f"({matched / n:.0%}), {matched_tonnes / total_tonnes:.0%} of latest-year tonnage"
    )


def _check_fluazinam(graph: TemporalGraph) -> None:
    """The V0 gate: the fluazinam structure is reconstructable and traversable."""
    node = graph.node(FLUAZINAM_ID)
    print(f"fluazinam node: {node.label} ({node.id})")

    products = [
        graph.node(e.subject).label
        for e in graph.edges_of(FLUAZINAM_ID)
        if e.predicate == EdgeType.CONTAINS
    ]
    print(f"  contained in {len(products)} products, e.g. {', '.join(sorted(products)[:5])}")

    paths = graph.evidence_paths(FLUAZINAM_ID, SWEDEN_ID, max_depth=2)
    direct = [p for p in paths if [e.predicate for e in p] == [EdgeType.APPROVED_IN]]
    print(f"  approved in Sweden: {'yes' if direct else 'no'} ({len(paths)} evidence paths <=2)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir", type=Path, default=PROCESSED)
    args = parser.parse_args()

    substances = _load(args.processed_dir / "kemi_register_substances.jsonl", Substance)
    products = _load(args.processed_dir / "kemi_register_products.jsonl", ProductRegistration)
    graph = build_from_register(substances, products)
    print(f"graph: {len(graph)} nodes, {graph.edge_count} edges")

    sales_path = args.processed_dir / "kemi_sales.jsonl"
    if sales_path.exists():
        resolver = SubstanceResolver(substances)
        _report_sales_coverage(resolver, _load(sales_path, SalesRecord))

    _check_fluazinam(graph)

    _write_jsonl(args.processed_dir / "graph_nodes.jsonl", graph.nodes())
    _write_jsonl(args.processed_dir / "graph_edges.jsonl", graph.edges())
    print(f"wrote graph to {args.processed_dir}/graph_{{nodes,edges}}.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
