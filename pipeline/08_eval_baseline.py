"""Run the V1 rolling-origin eval: XGBoost vs. three trivial baselines,
per cutoff, full-population and pesticide-subset, plus SHAP and the
fluazinam case-study readout.

This is the V1 gate deliverable (`V1_SCOPE.md`): a published eval table. If
XGBoost does not beat the trivial baselines, that is the honest result to
report, per the manifesto's baseline rule -- not a reason to keep tuning
until it wins.

Usage:
    python pipeline/08_eval_baseline.py
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
from pydantic import BaseModel

from hazium.explain.shap_baseline import explain_row, fit_and_explain, global_importance
from hazium.graph.build import load_graph
from hazium.ml.baseline import rolling_origin_eval
from hazium.ml.dataset import build_dataset
from hazium.ml.evaluate import summarize
from hazium.models import RegulatoryEvent, SalesRecord, Substance
from hazium.resolve.ids import safe_substance_node_id
from hazium.resolve.names import SubstanceResolver, resolve_sales_records

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"

CUTOFFS = [date(2018, 1, 1), date(2020, 1, 1), date(2022, 1, 1), date(2023, 1, 1)]
HEADLINE_CUTOFF = date(2023, 1, 1)
FLUAZINAM_ID = "substance:cas:79622-59-6"


def _load(path: Path, model: type[BaseModel]) -> list:
    with path.open(encoding="utf-8") as f:
        return [model.model_validate_json(line) for line in f]


def _pesticide_ids(register_substances: list[Substance]) -> set[str]:
    """Substance ids the KEMI register knows -- the pesticide-domain subset."""
    return {
        safe_substance_node_id(cas_number=s.cas_number, name=s.name) for s in register_substances
    }


def _print_table(rows: list[dict]) -> None:
    if not rows:
        return
    cols = [
        "cutoff",
        "model",
        "population",
        "positives",
        "average_precision",
        "ap_ci_lo",
        "ap_ci_hi",
    ]
    cols += [f"precision_at_{k}" for k in (10, 20, 50)]
    header = " | ".join(cols)
    print(header)
    print("|".join("---" for _ in cols))
    for row in rows:
        print(
            " | ".join(f"{row[c]:.3f}" if isinstance(row[c], float) else str(row[c]) for c in cols)
        )


def main() -> int:
    graph = load_graph(PROCESSED / "graph_nodes.jsonl", PROCESSED / "graph_edges.jsonl")
    register_substances = _load(PROCESSED / "kemi_register_substances.jsonl", Substance)
    resolver = SubstanceResolver(register_substances)
    sales = resolve_sales_records(_load(PROCESSED / "kemi_sales.jsonl", SalesRecord), resolver)
    regevents = _load(PROCESSED / "eu_ppdb_events.jsonl", RegulatoryEvent)
    pesticide_ids = _pesticide_ids(register_substances)
    print(f"pesticide-domain substances (KEMI register): {len(pesticide_ids)}")

    results = rolling_origin_eval(graph, sales, regevents, CUTOFFS)

    all_rows: list[dict] = []
    subset_rows: list[dict] = []
    for result in results:
        all_rows.extend(summarize(result))
        mask = np.array([sid in pesticide_ids for sid in result.ids])
        if mask.any():
            subset = type(result)(
                cutoff=result.cutoff,
                ids=[sid for sid, m in zip(result.ids, mask, strict=True) if m],
                y_true=result.y_true[mask],
                scores={name: s[mask] for name, s in result.scores.items()},
                out_of_fold=result.out_of_fold,
            )
            subset_rows.extend(summarize(subset))
        if not result.out_of_fold:
            print(
                f"NOTE: cutoff {result.cutoff} had <2 positives; "
                "XGBoost score is in-sample, not held-out."
            )

    print("\n=== Full population ===")
    _print_table(all_rows)
    print("\n=== Pesticide subset (KEMI register) ===")
    _print_table(subset_rows)

    # SHAP + fluazinam readout at the headline cutoff
    X, y, ids = build_dataset(graph, sales, regevents, HEADLINE_CUTOFF)
    print(f"\n=== SHAP global importance (cutoff {HEADLINE_CUTOFF}) ===")
    _, shap_values = fit_and_explain(X, y)
    for name, value in global_importance(shap_values):
        print(f"  {name}: {value:.4f}")

    print(f"\n=== Fluazinam case study (cutoff {HEADLINE_CUTOFF}) ===")
    if FLUAZINAM_ID in ids:
        headline_result = next(r for r in results if r.cutoff == HEADLINE_CUTOFF)
        rank = _rank_of(headline_result.ids, headline_result.scores["xgboost"], FLUAZINAM_ID)
        print(
            f"  XGBoost rank: {rank} of {headline_result.population} (label: negative -- see V1_SCOPE.md)"
        )
        for name, value in explain_row(shap_values, ids, FLUAZINAM_ID)[:5]:
            print(f"    {name}: {value:+.4f}")
    else:
        print(
            "  fluazinam not in this cutoff's population (already non-renewed, or no pre-cutoff fact)"
        )

    out_path = PROCESSED / "eval_results.json"
    out_path.write_text(
        json.dumps({"full_population": all_rows, "pesticide_subset": subset_rows}, indent=2),
        encoding="utf-8",
    )
    print(f"\nwrote eval table to {out_path}")
    return 0


def _rank_of(ids: list[str], scores: np.ndarray, target_id: str) -> int:
    order = np.argsort(-scores, kind="stable")
    ranked_ids = [ids[i] for i in order]
    return ranked_ids.index(target_id) + 1


if __name__ == "__main__":
    raise SystemExit(main())
