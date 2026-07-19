"""Build the V1 feature matrix and confirm the positive-class table.

Loads the merged graph plus sales and EU regulatory-event facts, then reports
the exact (not rough-estimated) population/positive counts per rolling-origin
cutoff -- the number `V1_SCOPE.md` flagged as needing confirmation once the
feature matrix exists. Also writes the headline-cutoff (2023-01-01) dataset
to CSV for inspection.

Usage:
    python pipeline/07_build_ml_dataset.py
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pydantic import BaseModel

from hazium.graph.build import load_graph
from hazium.ml.dataset import build_dataset
from hazium.models import LiteratureVolumeRecord, RegulatoryEvent, SalesRecord, Substance
from hazium.resolve.names import SubstanceResolver, resolve_sales_records

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"

CUTOFFS = [date(2018, 1, 1), date(2020, 1, 1), date(2022, 1, 1), date(2023, 1, 1)]
HEADLINE_CUTOFF = date(2023, 1, 1)


def _load(path: Path, model: type[BaseModel]) -> list:
    with path.open(encoding="utf-8") as f:
        return [model.model_validate_json(line) for line in f]


def _load_literature(path: Path) -> list[LiteratureVolumeRecord]:
    """Optional: the literature-volume fetch (`pipeline/14`) is long-running
    and may not have been run yet, or may still be in progress -- in either
    case an empty/partial file degrades gracefully to the feature's own
    documented no-signal default, never an error.
    """
    if not path.exists():
        return []
    return _load(path, LiteratureVolumeRecord)


def main() -> int:
    graph = load_graph(PROCESSED / "graph_nodes.jsonl", PROCESSED / "graph_edges.jsonl")
    sales_raw = _load(PROCESSED / "kemi_sales.jsonl", SalesRecord)
    regevents = _load(PROCESSED / "eu_ppdb_events.jsonl", RegulatoryEvent)
    register_substances = _load(PROCESSED / "kemi_register_substances.jsonl", Substance)
    resolver = SubstanceResolver(register_substances)
    sales = resolve_sales_records(sales_raw, resolver)
    resolved = sum(1 for s in sales if "cas:" in s.substance_id)
    lit_records = _load_literature(PROCESSED / "literature_volume.jsonl")
    print(f"graph: {len(graph)} nodes, {graph.edge_count} edges")
    print(f"sales records: {len(sales)} ({resolved} resolved to a CAS id)")
    print(f"regulatory events: {len(regevents)}")
    print(
        f"literature-volume records: {len(lit_records)}"
        f"{' (pipeline/14 not run yet -- feature will read as no-signal)' if not lit_records else ''}"
    )
    print()

    print("| cutoff | population | positives | base rate |")
    print("|---|---|---|---|")
    for cutoff in CUTOFFS:
        X, y, ids = build_dataset(graph, sales, regevents, cutoff, lit_records=lit_records)
        base_rate = y.mean() if len(y) else 0.0
        print(f"| {cutoff.isoformat()} | {len(ids)} | {int(y.sum())} | {base_rate:.2%} |")

    X, y, ids = build_dataset(graph, sales, regevents, HEADLINE_CUTOFF, lit_records=lit_records)
    out_path = PROCESSED / f"ml_dataset_{HEADLINE_CUTOFF.isoformat()}.csv"
    out = X.copy()
    out.insert(0, "substance_id", ids)
    out["label"] = y.to_numpy()
    out.to_csv(out_path, index=False)
    print(f"\nwrote headline-cutoff ({HEADLINE_CUTOFF}) dataset to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
