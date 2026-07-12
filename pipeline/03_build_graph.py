"""Build the graph from everything ingested so far, and verify the fluazinam
north-star.

Loads the register facts, builds the structure graph, joins the sales
substances onto it via the resolver (reporting coverage), layers in EFSA
OpenFoodTox structure if it has been ingested (dated evidence, degradation
edges), runs the fluazinam reconstruction as a live check, and serializes
nodes and edges to JSONL.

Usage:
    python pipeline/03_build_graph.py
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from pydantic import BaseModel

from hazium.graph.build import build_from_register, merge_clp, merge_eu_ppdb, merge_openfoodtox
from hazium.graph.store import TemporalGraph
from hazium.models import (
    DegradationLink,
    EdgeType,
    HazardClassification,
    ProductRegistration,
    RegulatoryEvent,
    SalesRecord,
    SourceDocument,
    Substance,
)
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

    degrades_to = [
        graph.node(e.object).label
        for e in graph.edges_of(FLUAZINAM_ID)
        if e.predicate == EdgeType.DEGRADES_TO and e.subject == FLUAZINAM_ID
    ]
    if degrades_to:
        print(f"  degrades to: {', '.join(degrades_to)}")

    classified_as = [
        (graph.node(e.object).label, e.known_at, e.attrs)
        for e in graph.edges_of(FLUAZINAM_ID)
        if e.predicate == EdgeType.CLASSIFIED_AS and e.subject == FLUAZINAM_ID
    ]
    for code, known_at, attrs in sorted(classified_as, key=lambda t: t[1]):
        hazard_class = f" ({attrs['hazard_class']})" if "hazard_class" in attrs else ""
        print(f"  classified as ({known_at}): {code}{hazard_class}")

    reg_events = [
        graph.node(e.object).label
        for e in graph.edges_of(FLUAZINAM_ID)
        if e.predicate == EdgeType.SUBJECT_OF and e.subject == FLUAZINAM_ID
    ]
    for label in sorted(reg_events):
        print(f"  regulatory event: {label}")

    evidence = [
        (graph.node(e.object).label, e.known_at)
        for e in graph.edges_of(FLUAZINAM_ID)
        if e.predicate == EdgeType.EVIDENCED_BY and e.subject == FLUAZINAM_ID
    ]
    for title, known_at in sorted(evidence, key=lambda t: t[1]):
        print(f"  evidenced by ({known_at}): {title}")

    pre_2023 = graph.as_of(date(2023, 1, 1))
    if pre_2023.has_node(FLUAZINAM_ID):
        pre_2023_evidence = [
            e for e in pre_2023.edges_of(FLUAZINAM_ID) if e.predicate == EdgeType.EVIDENCED_BY
        ]
        pre_2023_hazards = [
            e for e in pre_2023.edges_of(FLUAZINAM_ID) if e.predicate == EdgeType.CLASSIFIED_AS
        ]
        print(f"  evidence known before 2023-01-01: {len(pre_2023_evidence)} document(s)")
        print(f"  hazard classifications known before 2023-01-01: {len(pre_2023_hazards)}")


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

    oft_substances_path = args.processed_dir / "openfoodtox_substances.jsonl"
    if oft_substances_path.exists():
        oft_substances = _load(oft_substances_path, Substance)
        oft_links = _load(args.processed_dir / "openfoodtox_degradation.jsonl", DegradationLink)
        oft_documents = _load(args.processed_dir / "openfoodtox_assessments.jsonl", SourceDocument)
        merge_openfoodtox(graph, oft_substances, oft_links, oft_documents)
        print(
            f"merged OpenFoodTox: +{len(oft_substances)} substances, "
            f"{len(oft_links)} degradation links, {len(oft_documents)} dated assessments"
        )
        print(f"graph after merge: {len(graph)} nodes, {graph.edge_count} edges")

    clp_path = args.processed_dir / "clp_classifications.jsonl"
    if clp_path.exists():
        classifications = _load(clp_path, HazardClassification)
        applied, skipped = merge_clp(graph, classifications)
        print(
            f"merged CLP classifications: +{applied} applied "
            f"({skipped} skipped, substance not yet in graph)"
        )
        print(f"graph after merge: {len(graph)} nodes, {graph.edge_count} edges")

    ppdb_path = args.processed_dir / "eu_ppdb_events.jsonl"
    if ppdb_path.exists():
        events = _load(ppdb_path, RegulatoryEvent)
        applied, skipped = merge_eu_ppdb(graph, events)
        print(
            f"merged EU PPDB events: +{applied} applied "
            f"({skipped} skipped, substance not yet in graph)"
        )
        print(f"graph after merge: {len(graph)} nodes, {graph.edge_count} edges")

    _check_fluazinam(graph)

    _write_jsonl(args.processed_dir / "graph_nodes.jsonl", graph.nodes())
    _write_jsonl(args.processed_dir / "graph_edges.jsonl", graph.edges())
    print(f"wrote graph to {args.processed_dir}/graph_{{nodes,edges}}.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
