"""Run the Hazium Early Warning Benchmark (HEWB) and write its report.

The benchmark itself is pure (``benchmark/hewb.py``); this is the I/O boundary:
load the graph/sales/regulatory-events, run both label variants over annual
cutoffs, and write three report tables plus a human-readable summary. See
``BENCHMARK_SCOPE.md`` for the design and ``DEV_LOG.md`` for the published
result.

Success is a rigorous, reproducible, honestly-reported benchmark — not a high
lead-time number. Landmarks the model never flagged before their real action
are printed in the miss list, not hidden.

Usage:
    python pipeline/12_run_hewb.py
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from hazium.benchmark.hewb import K_VALUES, HewbReport, run_hewb
from hazium.graph.build import load_graph
from hazium.models import LiteratureVolumeRecord, RegulatoryEvent, SalesRecord, Substance
from hazium.resolve.names import SubstanceResolver, resolve_sales_records

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"


def _load(path: Path, model: type[BaseModel]) -> list:
    with path.open(encoding="utf-8") as f:
        return [model.model_validate_json(line) for line in f]


def _load_literature(path: Path) -> list[LiteratureVolumeRecord]:
    """Optional: degrades to the feature's no-signal default if not yet run."""
    if not path.exists():
        return []
    return _load(path, LiteratureVolumeRecord)


def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(",".join(header) + "\n")
        for row in rows:
            cells = []
            for value in row:
                text = "" if value is None else str(value)
                if any(c in text for c in (",", '"', "\n")):
                    text = '"' + text.replace('"', '""') + '"'
                cells.append(text)
            f.write(",".join(cells) + "\n")


def _write_aggregate(report: HewbReport) -> None:
    cols = [
        "variant",
        "cutoff",
        "model",
        "population",
        "positives",
        "average_precision",
        "ap_ci_lo",
        "ap_ci_hi",
        "precision_at_10",
        "precision_at_20",
        "precision_at_50",
    ]
    rows = [[r.get(c) for c in cols] for r in report.aggregate]
    _write_csv(PROCESSED / "hewb_aggregate.csv", cols, rows)


def _write_lead_times(report: HewbReport) -> None:
    cols = [
        "variant",
        "case",
        "cas",
        "action_date",
        "k",
        "first_flagged_cutoff",
        "lead_time_months",
    ]
    rows = []
    for cr in report.cases:
        if cr.action_date is None:
            continue  # no action under this variant: not a measurable case here
        for k in K_VALUES:
            first, months = cr.lead_times[k]
            rows.append(
                [
                    cr.variant,
                    cr.name,
                    cr.cas,
                    cr.action_date.isoformat(),
                    k,
                    first.isoformat() if first else "not_flagged",
                    months if months is not None else "",
                ]
            )
    _write_csv(PROCESSED / "hewb_lead_times.csv", cols, rows)


def _write_trajectories(report: HewbReport) -> None:
    cols = ["variant", "case", "cas", "cutoff", "rank", "population"]
    rows = []
    for cr in report.cases:
        for cutoff, rank, population in cr.trajectory:
            rows.append(
                [cr.variant, cr.name, cr.cas, cutoff.isoformat(), rank if rank else "", population]
            )
    _write_csv(PROCESSED / "hewb_rank_trajectories.csv", cols, rows)


def _write_embedding_comparison(report: HewbReport) -> None:
    if not report.embedding_comparison:
        return
    cols = [
        "variant",
        "cutoff",
        "model",
        "population",
        "positives",
        "average_precision",
        "ap_ci_lo",
        "ap_ci_hi",
        "source",
    ]
    rows = [[r.get(c) for c in cols] for r in report.embedding_comparison]
    _write_csv(PROCESSED / "hewb_embedding_comparison.csv", cols, rows)


def _print_summary(report: HewbReport) -> None:
    print(f"\n=== HEWB v{report.version} -- aggregate (xgboost vs. best trivial, per cutoff) ===")
    # Compact: for each variant/cutoff, xgboost AP vs. the best trivial AP.
    for variant in ("headline", "early_warning"):
        print(f"\n  [{variant}]")
        by_cutoff: dict[str, dict[str, float]] = {}
        for r in report.aggregate:
            if r["variant"] != variant:
                continue
            by_cutoff.setdefault(r["cutoff"], {})[r["model"]] = r["average_precision"]
        print(f"    {'cutoff':12s} {'xgboost AP':>11s} {'best trivial':>13s} {'positives':>10s}")
        for cutoff in sorted(by_cutoff):
            models = by_cutoff[cutoff]
            xgb = models.get("xgboost", 0.0)
            trivial = max(v for m, v in models.items() if m != "xgboost")
            pos = next(
                r["positives"]
                for r in report.aggregate
                if r["variant"] == variant and r["cutoff"] == cutoff and r["model"] == "xgboost"
            )
            print(f"    {cutoff:12s} {xgb:>11.3f} {trivial:>13.3f} {pos:>10d}")

    print("\n=== HEWB v{} -- lead times (months before real EU action) ===".format(report.version))
    for variant in ("headline", "early_warning"):
        measurable = [c for c in report.cases if c.variant == variant and c.action_date is not None]
        if not measurable:
            continue
        print(f"\n  [{variant}]  (lead time at k=10 / 20 / 50; 'miss' = never in top-k pre-action)")
        print(f"    {'case':22s} {'action':12s} {'k=10':>8s} {'k=20':>8s} {'k=50':>8s}")
        misses = []
        for cr in sorted(measurable, key=lambda c: c.action_date):

            def fmt(k: int, cr=cr) -> str:
                _, months = cr.lead_times[k]
                return f"{months}mo" if months is not None else "miss"

            print(
                f"    {cr.name:22s} {cr.action_date.isoformat():12s} "
                f"{fmt(10):>8s} {fmt(20):>8s} {fmt(50):>8s}"
            )
            if all(cr.lead_times[k][1] is None for k in K_VALUES):
                misses.append(cr.name)
        if misses:
            print(f"    MISSED (never in top-50 before action): {', '.join(misses)}")

    if report.embedding_comparison:
        print(
            f"\n=== HEWB v{report.version} -- frozen V2 embedding comparison "
            "(from V2b, 2-year cutoffs, NOT re-run at annual granularity -- see "
            "embedding_comparison_rows docstring for why) ==="
        )
        by_key: dict[tuple[str, str], dict[str, float]] = {}
        for r in report.embedding_comparison:
            by_key.setdefault((r["variant"], r["cutoff"]), {})[r["model"]] = r["average_precision"]
        for variant in ("headline", "early_warning"):
            rows = {k: v for k, v in by_key.items() if k[0] == variant}
            if not rows:
                continue
            print(f"\n  [{variant}]")
            print(
                f"    {'cutoff':12s} {'tabular AP':>11s} {'embed_only AP':>14s} "
                f"{'tabular+embed AP':>18s}"
            )
            for (_v, cutoff), models in sorted(rows.items()):
                print(
                    f"    {cutoff:12s} {models.get('xgboost_tabular', 0.0):>11.3f} "
                    f"{models.get('xgboost_embed_only', 0.0):>14.3f} "
                    f"{models.get('xgboost_tabular_plus_embed', 0.0):>18.3f}"
                )
    else:
        print(
            f"\n=== HEWB v{report.version} -- embedding comparison: SKIPPED "
            "(no data/processed/embed_eval_results.json found; run pipeline/10 first) ==="
        )


def main() -> int:
    graph = load_graph(PROCESSED / "graph_nodes.jsonl", PROCESSED / "graph_edges.jsonl")
    register_substances = _load(PROCESSED / "kemi_register_substances.jsonl", Substance)
    resolver = SubstanceResolver(register_substances)
    sales = resolve_sales_records(_load(PROCESSED / "kemi_sales.jsonl", SalesRecord), resolver)
    regevents = _load(PROCESSED / "eu_ppdb_events.jsonl", RegulatoryEvent)
    kemi_reeval_path = PROCESSED / "kemi_reevaluations.jsonl"
    if kemi_reeval_path.exists():
        regevents += _load(kemi_reeval_path, RegulatoryEvent)
    lit_records = _load_literature(PROCESSED / "literature_volume.jsonl")
    print(f"literature-volume records: {len(lit_records)}")

    v2b_path = PROCESSED / "embed_eval_results.json"
    v2b_embedding_json = (
        json.loads(v2b_path.read_text(encoding="utf-8")) if v2b_path.exists() else None
    )

    report = run_hewb(
        graph, sales, regevents, v2b_embedding_json=v2b_embedding_json, lit_records=lit_records
    )

    _write_aggregate(report)
    _write_lead_times(report)
    _write_trajectories(report)
    _write_embedding_comparison(report)
    _print_summary(report)

    print(f"\nwrote HEWB v{report.version} tables to {PROCESSED}")
    written = ["hewb_aggregate.csv", "hewb_lead_times.csv", "hewb_rank_trajectories.csv"]
    if report.embedding_comparison:
        written.append("hewb_embedding_comparison.csv")
    print("  " + ", ".join(written))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
