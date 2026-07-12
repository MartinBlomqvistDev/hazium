"""Run the V2b comparison: tabular baseline vs. metapath2vec embedding alone
vs. tabular+embedding concatenated, per cutoff, both label variants.

This is the actual V2 gate (`V2_SCOPE.md`): the embedding is fit fresh on
each cutoff's `as_of(T)` view (`ml/embed.py`, `ml/baseline.py`'s
`evaluate_cutoff_with_embeddings`), never on the full graph. If neither
`xgboost_embed_only` nor `xgboost_tabular_plus_embed` beats `xgboost_tabular`
by more than the bootstrap CI, the tabular baseline remains the published
result and this is a documented negative -- a valid, gate-passing outcome
per the manifesto's baseline rule, not a failure to fix.

Usage:
    python pipeline/10_embed_eval.py
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
from pydantic import BaseModel

from hazium.graph.build import load_graph
from hazium.ml.baseline import CutoffResult, rolling_origin_eval_with_embeddings
from hazium.ml.dataset import DEFAULT_POSITIVE_KINDS, EARLY_WARNING_POSITIVE_KINDS
from hazium.ml.evaluate import average_precision, bootstrap_ci, summarize
from hazium.models import RegulatoryEvent, RegulatoryEventKind, SalesRecord, Substance
from hazium.resolve.names import SubstanceResolver, resolve_sales_records

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"

CUTOFFS = [date(2018, 1, 1), date(2020, 1, 1), date(2022, 1, 1), date(2023, 1, 1)]
HEADLINE_CUTOFF = date(2023, 1, 1)
FLUAZINAM_ID = "substance:cas:79622-59-6"

VARIANTS: tuple[tuple[str, frozenset[RegulatoryEventKind]], ...] = (
    ("headline (EU non-renewal only)", DEFAULT_POSITIVE_KINDS),
    ("early_warning (+ SE reevaluation)", EARLY_WARNING_POSITIVE_KINDS),
)

CONDITIONS = ("xgboost_tabular", "xgboost_embed_only", "xgboost_tabular_plus_embed")


def _load(path: Path, model: type[BaseModel]) -> list:
    with path.open(encoding="utf-8") as f:
        return [model.model_validate_json(line) for line in f]


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


def _rank_of(ids: list[str], scores: np.ndarray, target_id: str) -> int:
    order = np.argsort(-scores, kind="stable")
    ranked_ids = [ids[i] for i in order]
    return ranked_ids.index(target_id) + 1


def _verdict(result: CutoffResult) -> str:
    """Does either embedding condition beat tabular-alone, CI included?

    "Beats" means the challenger's AP exceeds tabular's AP *and* the
    challenger's own lower CI bound clears tabular's point estimate -- a
    stricter bar than a bare point-estimate comparison, matching the gate's
    "beats ... by more than the bootstrap CI" wording.
    """
    tabular_ap = average_precision(result.y_true, result.scores["xgboost_tabular"])
    lines = [f"    xgboost_tabular: AP={tabular_ap:.3f} (reference)"]
    any_win = False
    for name in ("xgboost_embed_only", "xgboost_tabular_plus_embed"):
        scores = result.scores[name]
        ap = average_precision(result.y_true, scores)
        lo, _hi = bootstrap_ci(result.y_true, scores, average_precision)
        beats = ap > tabular_ap and lo > tabular_ap
        any_win = any_win or beats
        lines.append(f"    {name}: AP={ap:.3f} (CI lower bound {lo:.3f}) -> beats tabular: {beats}")
    lines.append(f"    VERDICT: {'embedding wins' if any_win else 'documented negative'}")
    return "\n".join(lines)


def main() -> int:
    graph = load_graph(PROCESSED / "graph_nodes.jsonl", PROCESSED / "graph_edges.jsonl")
    register_substances = _load(PROCESSED / "kemi_register_substances.jsonl", Substance)
    resolver = SubstanceResolver(register_substances)
    sales = resolve_sales_records(_load(PROCESSED / "kemi_sales.jsonl", SalesRecord), resolver)
    regevents = _load(PROCESSED / "eu_ppdb_events.jsonl", RegulatoryEvent)
    kemi_reeval_path = PROCESSED / "kemi_reevaluations.jsonl"
    if kemi_reeval_path.exists():
        regevents += _load(kemi_reeval_path, RegulatoryEvent)

    output: dict[str, dict] = {}

    for label, positive_kinds in VARIANTS:
        print(f"\n{'#' * 70}\n# Variant: {label}\n{'#' * 70}")
        results = rolling_origin_eval_with_embeddings(
            graph, sales, regevents, CUTOFFS, positive_kinds=positive_kinds
        )

        all_rows: list[dict] = []
        for result in results:
            all_rows.extend(summarize(result))
            if not result.out_of_fold:
                print(
                    f"NOTE: cutoff {result.cutoff} had <2 positives; "
                    "XGBoost scores are in-sample, not held-out."
                )

        print("\n=== Full population ===")
        _print_table(all_rows)

        print("\n=== Per-cutoff verdict: does embedding beat tabular-alone? ===")
        for result in results:
            print(f"  cutoff {result.cutoff}:")
            print(_verdict(result))

        headline_result = next(r for r in results if r.cutoff == HEADLINE_CUTOFF)
        print(f"\n=== Fluazinam case study (cutoff {HEADLINE_CUTOFF}) ===")
        if FLUAZINAM_ID in headline_result.ids:
            label_value = int(headline_result.y_true[headline_result.ids.index(FLUAZINAM_ID)])
            print(f"  label: {label_value}")
            for condition in CONDITIONS:
                rank = _rank_of(
                    headline_result.ids, headline_result.scores[condition], FLUAZINAM_ID
                )
                print(f"  {condition} rank: {rank} of {headline_result.population}")
        else:
            print("  fluazinam not in this cutoff's population (already realized, or no fact yet)")

        output[label] = {"full_population": all_rows}

    out_path = PROCESSED / "embed_eval_results.json"
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"\nwrote embedding eval table (both variants) to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
