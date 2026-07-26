"""Run the survival evaluation: does the evidence predict who fails, not when?

HEWB's headline is reproducible by ranking on approval age alone, because its
target mixes *whether* a substance was withdrawn with *when*. This re-runs the
same features against a target that separates them: one approved substance in
one year at risk, outcome inside a horizon starting that year.

Every arm uses folds grouped by substance, so a substance's years never straddle
a split and no model can memorise one across folds. The forward arm is stricter
still and splits on time alone, which is the only arm that resembles deployment.

Usage:
    python pipeline/28_run_survival.py
    python pipeline/28_run_survival.py --horizon 2 --seeds 5
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold

from hazium.benchmark.survival import (
    EVENT,
    EVIDENCE_GROUPS,
    IN_FUNNEL_GROUPS,
    SUBJECT,
    PanelSpec,
    baseline_hazard,
    build_panel,
    feature_columns,
    forward_split,
)
from hazium.graph.build import load_graph
from hazium.ml.baseline import make_model
from hazium.models import LiteratureVolumeRecord, RegulatoryEvent, SalesRecord, Substance
from hazium.resolve.names import SubstanceResolver, resolve_sales_records
from hazium.sources.echa_clh import clh_intention_records, earliest_intention_year

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"
#: ECHA intentions to submit a harmonised classification. Read from the raw
#: snapshot like `pipeline/12` does, so the panel carries the same feature
#: groups the v1.4 benchmark did rather than a silently empty one.
CLH_SNAPSHOT = ROOT / "data" / "raw" / "clh_intentions_ppp.jsonl"

#: Folds for the grouped evaluation. Five keeps at least a few events per fold
#: at the observed event count without leaving any fold empty.
N_SPLITS = 5


def _load(path: Path, model):
    with path.open(encoding="utf-8") as f:
        return [model.model_validate_json(line) for line in f]


def grouped_scores(panel, columns: list[str], seed: int) -> np.ndarray:
    """Out-of-fold predictions with folds grouped by substance."""
    X, y, groups = panel[columns], panel[EVENT], panel[SUBJECT]
    out = np.zeros(len(y))
    splitter = StratifiedGroupKFold(n_splits=N_SPLITS, shuffle=True, random_state=seed)
    for train_idx, test_idx in splitter.split(X, y, groups):
        model = make_model(y.iloc[train_idx], seed)
        model.fit(X.iloc[train_idx], y.iloc[train_idx])
        out[test_idx] = model.predict_proba(X.iloc[test_idx])[:, 1]
    return out


def arm(panel, columns: list[str], seeds: range) -> tuple[float, float, float]:
    """Mean average precision, its spread across seeds, and mean AUC."""
    y = panel[EVENT].to_numpy()
    aps, aucs = [], []
    for seed in seeds:
        scores = grouped_scores(panel, columns, seed)
        aps.append(average_precision_score(y, scores))
        aucs.append(roc_auc_score(y, scores))
    return float(np.mean(aps)), float(np.std(aps)), float(np.mean(aucs))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--horizon", type=int, default=1, help="outcome window in years")
    parser.add_argument("--seeds", type=int, default=3, help="seeds per arm")
    args = parser.parse_args()
    seeds = range(42, 42 + args.seeds)

    graph = load_graph(PROCESSED / "graph_nodes.jsonl", PROCESSED / "graph_edges.jsonl")
    sales = resolve_sales_records(
        _load(PROCESSED / "kemi_sales.jsonl", SalesRecord),
        SubstanceResolver(_load(PROCESSED / "kemi_register_substances.jsonl", Substance)),
    )
    events = _load(PROCESSED / "eu_ppdb_events.jsonl", RegulatoryEvent)
    lit = _load(PROCESSED / "literature_volume.jsonl", LiteratureVolumeRecord)
    clh = (
        clh_intention_records(earliest_intention_year(CLH_SNAPSHOT))
        if CLH_SNAPSHOT.exists()
        else []
    )
    print(f"CLH-intention records: {len(clh)}")

    panel = build_panel(
        graph, sales, events, lit, PanelSpec(horizon_years=args.horizon), clh_records=clh
    )
    y = panel[EVENT].to_numpy()
    base = y.mean()
    print(
        f"panel: {len(panel):,} substance-years, {panel[SUBJECT].nunique():,} substances, "
        f"{int(y.sum())} events, base rate {base:.2%}, horizon {args.horizon}y\n"
    )

    print("baseline hazard by approval age (no model)")
    for row in baseline_hazard(panel).itertuples():
        span = f"{row.age_from}-{row.age_to if row.age_to < 99 else '+'}y"
        print(f"  {span:<7} rows {row.rows:>5}  events {row.events:>3}  hazard {row.hazard:>6.2%}")
    print()

    arms = {
        "age only": feature_columns(age=True, evidence=False),
        "evidence only": feature_columns(age=False, evidence=True),
        "age + evidence": feature_columns(),
    }
    results: dict[str, tuple[float, float, float]] = {}
    print("grouped by substance, out-of-fold")
    for name, cols in arms.items():
        ap, sd, auc = arm(panel, cols, seeds)
        results[name] = (ap, sd, auc)
        print(f"  {name:<16} AP {ap:.4f} (+/-{sd:.4f})  lift {ap / base:>5.2f}x  AUC {auc:.3f}")

    ap_age = results["age only"][0]
    ap_both, sd_both, _ = results["age + evidence"]
    tolerance = 2 * max(results["age only"][1], sd_both)
    delta = ap_both - ap_age
    verdict = "evidence adds signal" if delta > tolerance else "within noise"
    print(f"\n  delta {delta:+.4f} against tolerance +/-{tolerance:.4f}  ->  {verdict}\n")

    print("each evidence group added to age on its own")
    group_rows = []
    for name in EVIDENCE_GROUPS:
        ap, _sd, _auc = arm(panel, feature_columns(age=True, groups=(name,)), seeds)
        group_rows.append((name, ap, ap - ap_age))
        print(f"  age + {name:<12} AP {ap:.4f}  delta {ap - ap_age:+.4f}")
    print()

    # EFSA activity and ECHA CLH intentions read the regulator's own pipeline.
    # If the whole gain came from those, the model would be reporting regulatory
    # intent rather than anticipating it, so the two blocks are measured apart.
    print("in-funnel (efsa, clh) against out-of-funnel (clp, sales, graph, literature)")
    block_rows = []
    for label, names in (
        ("in_funnel", tuple(sorted(IN_FUNNEL_GROUPS))),
        ("out_of_funnel", tuple(n for n in EVIDENCE_GROUPS if n not in IN_FUNNEL_GROUPS)),
    ):
        ap, _sd, _auc = arm(panel, feature_columns(age=True, groups=names), seeds)
        block_rows.append((label, ap, ap - ap_age))
        print(f"  age + {label:<14} AP {ap:.4f}  delta {ap - ap_age:+.4f}")
    print()

    print("forward splits: fit on <=Y, score every later year")
    forward_rows = []
    for cut in range(2014, 2023):
        train, test = forward_split(panel, cut)
        n_train_events = int(panel[EVENT][train].sum())
        n_test_events = int(panel[EVENT][test].sum())
        if n_train_events < 3 or n_test_events < 3:
            continue
        y_test = panel[EVENT][test].to_numpy()
        scored = {}
        for label, cols in (("age", arms["age only"]), ("both", arms["age + evidence"])):
            model = make_model(panel[EVENT][train], 42)
            model.fit(panel[cols][train], panel[EVENT][train])
            scored[label] = model.predict_proba(panel[cols][test])[:, 1]
        ap_a = average_precision_score(y_test, scored["age"])
        ap_b = average_precision_score(y_test, scored["both"])
        top50 = {label: int(y_test[np.argsort(-s)[:50]].sum()) for label, s in scored.items()}
        forward_rows.append((cut, n_train_events, n_test_events, ap_a, ap_b, top50))
        print(
            f"  <={cut}  train ev {n_train_events:>3}  test ev {n_test_events:>3}  "
            f"age {ap_a:.4f}  both {ap_b:.4f}  delta {ap_b - ap_a:+.4f}  "
            f"hits@50 {top50['age']} vs {top50['both']}"
        )
    if forward_rows:
        mean_delta = float(np.mean([r[4] - r[3] for r in forward_rows]))
        positive = sum(1 for r in forward_rows if r[4] > r[3])
        print(
            f"\n  all splits: positive in {positive} of {len(forward_rows)}, "
            f"mean delta {mean_delta:+.4f}"
        )
        # The early splits used to be reported as failing below a sixteen-event
        # floor. A subsampling test disproved that: holding the test set fixed
        # and varying only the training events, the delta stays positive down to
        # four. What the early splits fail at is transfer between regulatory
        # eras, so they are named by era here rather than by sample size.
        negative = [r[0] for r in forward_rows if r[4] <= r[3]]
        if negative:
            print(
                f"  negative or flat when fitted through {', '.join(str(c) for c in negative)}: "
                "training before the 2017-2021 renewal wave does not transfer into it."
            )

    out = PROCESSED / f"survival_h{args.horizon}.csv"
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["arm", "average_precision", "seed_sd", "auc", "lift"])
        for name, (ap, sd, auc) in results.items():
            writer.writerow([name, f"{ap:.6f}", f"{sd:.6f}", f"{auc:.6f}", f"{ap / base:.4f}"])
        writer.writerow([])
        writer.writerow(["group_added_to_age", "average_precision", "delta"])
        for name, ap, d in group_rows:
            writer.writerow([name, f"{ap:.6f}", f"{d:+.6f}"])
        writer.writerow([])
        writer.writerow(["evidence_block_added_to_age", "average_precision", "delta"])
        for name, ap, d in block_rows:
            writer.writerow([name, f"{ap:.6f}", f"{d:+.6f}"])
        writer.writerow([])
        writer.writerow(
            [
                "train_through",
                "train_events",
                "test_events",
                "age_ap",
                "both_ap",
                "age_hits_at_50",
                "both_hits_at_50",
            ]
        )
        for cut, ntr, nte, a, b, t in forward_rows:
            writer.writerow([cut, ntr, nte, f"{a:.6f}", f"{b:.6f}", t["age"], t["both"]])
    print(f"\nwrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
