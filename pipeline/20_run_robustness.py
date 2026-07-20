"""Run the robustness capstone and write its report.

The tests are pure (``benchmark/robustness.py`` and ``explain/shap_baseline.py``);
this is the I/O boundary. Loads the same graph/sales/regulatory-events/literature/
CLH inputs as ``pipeline/12_run_hewb.py`` (so every rank here is comparable to a
HEWB rank), derives the negative-control substance sets from the regulatory
events, runs four tests, writes their report tables, and prints a human-readable
summary.

Per ``STRATEGY_SCOPE.md`` Move 1. Success is a robustness section that survives a
skeptical domain reader, not a flattering number:

* the label-shuffle placebo must *collapse* (a shuffled label scoring like the
  real one is the honest kill signal, printed as such);
* the cutoff-sweep should show the aggregate lead over baseline holding across
  2020-2024 and the north-star (fluazinam) rank stable, not a 2023 accident;
* the negative controls (reviewed-but-not-banned) should rank below the true
  positives, not concentrate at the top;
* the SHAP funnel split should show the outside-funnel literature feature
  carrying real weight, not the model merely reading the regulator's pipeline.

Usage:
    python pipeline/20_run_robustness.py                 # full run
    python pipeline/20_run_robustness.py --quick         # fast smoke run
    python pipeline/20_run_robustness.py --permutations 100
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from pydantic import BaseModel

from hazium.benchmark.hewb import LANDMARK_CASES
from hazium.benchmark.robustness import (
    PLACEBO_PERMUTATIONS,
    PLACEBO_REPEATS,
    cutoff_sweep,
    label_shuffle_placebo,
    negative_controls,
)
from hazium.graph.build import load_graph
from hazium.ml.baseline import evaluate_cutoff
from hazium.ml.dataset import (
    DEFAULT_POSITIVE_KINDS,
    EARLY_WARNING_POSITIVE_KINDS,
    build_dataset,
)
from hazium.explain.shap_baseline import (
    fit_and_explain,
    global_importance,
    grouped_importance,
)
from hazium.models import (
    LiteratureVolumeRecord,
    RegulatoryEvent,
    RegulatoryEventKind,
    SalesRecord,
    Substance,
)
from hazium.resolve.names import SubstanceResolver, resolve_sales_records
from hazium.sources.echa_clh import clh_intention_records, earliest_intention_year

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"

#: The headline cutoff the placebo and the negative-control specificity test run
#: at — the same 2023-01-01 the public site and README lead with.
HEADLINE_CUTOFF = date(2023, 1, 1)

#: The cutoff-sweep answers "is 2023 cherry-picked?" directly: five recent
#: annual cutoffs. The aggregate AP at each shows the model's lead over the
#: trivial baselines is not a 2023 accident; fluazinam's rank across the same
#: cutoffs shows the north-star number the site leads with is representative.
SWEEP_CUTOFFS = tuple(date(y, 1, 1) for y in range(2020, 2025))

VARIANTS = (
    ("headline", DEFAULT_POSITIVE_KINDS),
    ("early_warning", EARLY_WARNING_POSITIVE_KINDS),
)

SEVERE_HAZARD_COLUMNS = ("clp_has_cmr", "clp_has_aquatic_chronic_1", "clp_has_stot")


def _load(path: Path, model: type[BaseModel]) -> list:
    with path.open(encoding="utf-8") as f:
        return [model.model_validate_json(line) for line in f]


def _load_literature(path: Path) -> list[LiteratureVolumeRecord]:
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


def _survivor_ids(regevents: list[RegulatoryEvent]) -> set[str]:
    """Substances that entered the EU regime and were never non-renewed.

    ``approved`` and never ``non_renewal``. In this pipeline's EU PPDB export
    the only two event kinds present are ``approval`` and ``non_renewal`` (no
    explicit ``renewal`` events are published in the bulk file), so "approved
    and still standing" is the honest, data-available proxy for "went through EU
    review and was not banned". Stated plainly in the DEV_LOG so no reader
    mistakes this for a curated post-renewal set.
    """
    approved = {e.substance_id for e in regevents if e.kind == RegulatoryEventKind.APPROVAL}
    non_renewed = {e.substance_id for e in regevents if e.kind == RegulatoryEventKind.NON_RENEWAL}
    return approved - non_renewed


def _hazardous_ids(
    graph, sales, regevents, cutoff, positive_kinds, lit_records, clh_records
) -> set[str]:
    """Population members carrying >=1 severe hazard flag at the cutoff.

    The design matrix, not scoring — cheap. Used to intersect with the survivor
    set to build the sharpest control: substances that *look* dangerous (CMR /
    aquatic-chronic-1 / STOT) yet were never actioned. If the model just flagged
    hazardous chemicals, these would sit at the top.
    """
    X, _y, _ids = build_dataset(
        graph, sales, regevents, cutoff, positive_kinds, lit_records, clh_records
    )
    mask = (X[list(SEVERE_HAZARD_COLUMNS)].to_numpy() > 0).any(axis=1)
    return {sid for sid, hazardous in zip(X.index, mask) if hazardous}


def _print_placebo(results) -> None:
    print("\n=== Robustness 1/4 -- label-shuffle placebo (the kill-criterion) ===")
    print("  Null keeps class balance, breaks feature<->label link. Real AP must")
    print("  tower over the shuffled null; a shuffled AP reaching it retracts the result.\n")
    print(
        f"    {'variant':14s} {'base_rate':>10s} {'real_AP':>9s} "
        f"{'null_mean':>10s} {'null_p95':>9s} {'null_max':>9s} {'p_value':>8s}"
    )
    for r in results:
        verdict = "COLLAPSES [pass]" if r.real_ap > 5 * r.shuffled_max else "CHECK"
        print(
            f"    {r.variant:14s} {r.base_rate:>10.4f} {r.real_ap:>9.4f} "
            f"{r.shuffled_mean:>10.4f} {r.shuffled_p95:>9.4f} {r.shuffled_max:>9.4f} "
            f"{r.p_value:>8.3f}  {verdict}"
        )


def _print_sweep(aggregate, ranks) -> None:
    print("\n=== Robustness 2/4 -- cutoff-sweep (is 2023 cherry-picked?) ===")
    cutoffs = sorted({r.cutoff for r in aggregate})

    print("  (a) Aggregate lead over baseline at each cutoff. XGBoost AP should")
    print("      tower over the best trivial baseline at every cutoff, not just 2023.\n")
    for variant in ("headline", "early_warning"):
        vagg = [r for r in aggregate if r.variant == variant]
        if not vagg:
            continue
        print(f"  [{variant}]")
        print(
            f"    {'cutoff':>8s} {'pop':>6s} {'pos':>4s} "
            f"{'base_rate':>10s} {'xgb_AP':>8s} {'trivial_AP':>11s} {'ratio':>7s}"
        )
        for r in sorted(vagg, key=lambda x: x.cutoff):
            ratio = r.xgboost_ap / r.best_trivial_ap if r.best_trivial_ap else float("inf")
            ratio_s = "inf" if ratio == float("inf") else f"{ratio:.1f}x"
            print(
                f"    {r.cutoff.year:>8d} {r.population:>6d} {r.positives:>4d} "
                f"{r.base_rate:>10.4f} {r.xgboost_ap:>8.4f} {r.best_trivial_ap:>11.4f} {ratio_s:>7s}"
            )
        print()

    print("  (b) North-star (fluazinam) + landmark ranks across the same cutoffs.")
    print("      '-' = censored out (already actioned) or no pre-cutoff fact.\n")
    for variant in ("headline", "early_warning"):
        vrows = [r for r in ranks if r.variant == variant]
        if not vrows:
            continue
        # Only show substances that appear in the population at >=1 cutoff.
        present_names = sorted({r.name for r in vrows if r.rank is not None})
        if not present_names:
            continue
        print(f"  [{variant}]")
        print("    {:22s}".format("substance") + "".join(f"{c.year:>8d}" for c in cutoffs))
        for name in present_names:
            cells = ""
            for c in cutoffs:
                match = next((r for r in vrows if r.name == name and r.cutoff == c), None)
                cells += f"{('-' if match is None or match.rank is None else match.rank):>8}"
            print(f"    {name:22s}{cells}")
        print()


def _print_controls(results) -> None:
    print("\n=== Robustness 3/4 -- negative controls (does it just flag hazard?) ===")
    print("  Reviewed-but-not-banned substances should NOT concentrate at the top.")
    print("  Low top-k counts + a deep median percentile => the model is specific.\n")
    print(
        f"    {'variant':14s} {'group':22s} {'n':>5s} "
        f"{'top10':>6s} {'top20':>6s} {'top50':>6s} {'med_rank':>9s} {'med_pctile':>11s}"
    )
    for r in results:
        med_rank = "-" if r.median_rank is None else f"{r.median_rank:.0f}"
        med_pct = "-" if r.median_percentile is None else f"{r.median_percentile:.1%}"
        print(
            f"    {r.variant:14s} {r.label:22s} {r.n_present:>5d} "
            f"{r.in_top_k.get(10, 0):>6d} {r.in_top_k.get(20, 0):>6d} {r.in_top_k.get(50, 0):>6d} "
            f"{med_rank:>9s} {med_pct:>11s}"
        )


def _print_shap(shap_results) -> None:
    print("\n=== Robustness 4/4 -- SHAP funnel split (is the edge outside the funnel?) ===")
    print("  Inside-funnel = reading the regulator's pipeline (proves little); outside-funnel")
    print("  = independent literature (the differentiation). A meaningful outside share means")
    print("  the model saw signal the paperwork had not yet shown.\n")
    for variant, funnel_rows, top_features in shap_results:
        print(f"  [{variant}]  funnel-group share of total mean|SHAP|")
        for r in sorted(funnel_rows, key=lambda x: -x["share"]):
            print(f"    {r['group']:16s} {r['share']:>7.1%}  (mean|SHAP| {r['mean_abs_shap']:.4f})")
        top = ", ".join(f"{name} {val:.3f}" for name, val in top_features)
        print(f"    top features: {top}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Hazium robustness capstone.")
    parser.add_argument(
        "--permutations",
        type=int,
        default=PLACEBO_PERMUTATIONS,
        help=f"label-shuffle permutations for the placebo null (default {PLACEBO_PERMUTATIONS})",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=PLACEBO_REPEATS,
        help=f"CV repeats per placebo fit (default {PLACEBO_REPEATS})",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="fast smoke run: 5 permutations, headline variant only (not for reporting)",
    )
    args = parser.parse_args()

    permutations = 5 if args.quick else args.permutations
    variants = VARIANTS[:1] if args.quick else VARIANTS

    graph = load_graph(PROCESSED / "graph_nodes.jsonl", PROCESSED / "graph_edges.jsonl")
    register_substances = _load(PROCESSED / "kemi_register_substances.jsonl", Substance)
    resolver = SubstanceResolver(register_substances)
    sales = resolve_sales_records(_load(PROCESSED / "kemi_sales.jsonl", SalesRecord), resolver)
    regevents = _load(PROCESSED / "eu_ppdb_events.jsonl", RegulatoryEvent)
    kemi_reeval_path = PROCESSED / "kemi_reevaluations.jsonl"
    if kemi_reeval_path.exists():
        regevents += _load(kemi_reeval_path, RegulatoryEvent)
    lit_records = _load_literature(PROCESSED / "literature_volume.jsonl")
    clh_snapshot = ROOT / "data" / "raw" / "clh_intentions_ppp.jsonl"
    clh_records = (
        clh_intention_records(earliest_intention_year(clh_snapshot))
        if clh_snapshot.exists()
        else []
    )
    print(
        f"loaded: {len(sales)} sales, {len(regevents)} reg-events, "
        f"{len(lit_records)} literature, {len(clh_records)} CLH"
    )
    print(
        f"placebo config: {permutations} permutations x {args.repeats} repeats, "
        f"cutoff {HEADLINE_CUTOFF.isoformat()}"
    )

    survivors = _survivor_ids(regevents)
    print(f"negative-control survivor set: {len(survivors)} approved-and-never-non-renewed\n")

    landmark_targets = [(c.name, c.cas) for c in LANDMARK_CASES]

    placebo_results = []
    sweep_aggregate = []
    sweep_ranks = []
    control_results = []
    shap_results = []  # (variant, funnel_rows, top_features)

    for variant, positive_kinds in variants:
        print(f"--- {variant} ---")
        # 1. Placebo at the headline cutoff.
        X, y, _ids = build_dataset(
            graph, sales, regevents, HEADLINE_CUTOFF, positive_kinds, lit_records, clh_records
        )
        placebo_results.append(
            label_shuffle_placebo(
                X, y, variant, HEADLINE_CUTOFF, n_permutations=permutations, repeats=args.repeats
            )
        )

        # 4. SHAP inside-vs-outside-funnel split on the same headline model.
        #    In-sample fit is correct here: SHAP explains what the fitted model
        #    learned to weight, a different question from the out-of-fold ranking.
        _model, shap_values = fit_and_explain(X, y)
        shap_results.append(
            (variant, grouped_importance(shap_values), global_importance(shap_values)[:6])
        )

        # 2. Cutoff-sweep: aggregate AP + landmark/north-star ranks per cutoff.
        sweep = cutoff_sweep(
            graph,
            sales,
            regevents,
            list(SWEEP_CUTOFFS),
            landmark_targets,
            variant,
            positive_kinds=positive_kinds,
            lit_records=lit_records,
            clh_records=clh_records,
        )
        sweep_aggregate.extend(sweep.aggregate)
        sweep_ranks.extend(sweep.ranks)

        # 3. Negative controls at the headline cutoff (reuse one scored result).
        headline_result = evaluate_cutoff(
            graph,
            sales,
            regevents,
            HEADLINE_CUTOFF,
            positive_kinds=positive_kinds,
            lit_records=lit_records,
            clh_records=clh_records,
        )
        hazardous = _hazardous_ids(
            graph, sales, regevents, HEADLINE_CUTOFF, positive_kinds, lit_records, clh_records
        )
        # The true future-action positives are the reference: the specificity
        # claim is a *contrast* (positives cluster tight at the top; survivors,
        # even hazardous ones, do not), not an absolute survivor rank. Approved
        # pesticides are the feature-rich substances in a mostly-inert
        # ~5,900-node population, so they naturally out-rank random graph nodes;
        # what must hold is that they rank well below the substances actually
        # actioned.
        positive_ids = {
            sid for sid, y in zip(headline_result.ids, headline_result.y_true) if y == 1
        }
        control_results.extend(
            negative_controls(
                headline_result,
                {
                    "future_positives (ref)": positive_ids,
                    "approved_survivors": survivors,
                    "hazardous_survivors": survivors & hazardous,
                },
                variant,
            )
        )

    _print_placebo(placebo_results)
    _print_sweep(sweep_aggregate, sweep_ranks)
    _print_controls(control_results)
    _print_shap(shap_results)

    if args.quick:
        print("\n(--quick run: results are a smoke test, not for reporting)")
        return 0

    _write_csv(
        PROCESSED / "robustness_placebo.csv",
        [
            "variant",
            "cutoff",
            "population",
            "positives",
            "base_rate",
            "real_ap",
            "shuffled_mean",
            "shuffled_p95",
            "shuffled_max",
            "p_value",
            "n_permutations",
            "repeats",
        ],
        [
            [
                r.variant,
                r.cutoff.isoformat(),
                r.population,
                r.positives,
                round(r.base_rate, 6),
                round(r.real_ap, 6),
                round(r.shuffled_mean, 6),
                round(r.shuffled_p95, 6),
                round(r.shuffled_max, 6),
                round(r.p_value, 6),
                r.n_permutations,
                r.repeats,
            ]
            for r in placebo_results
        ],
    )
    _write_csv(
        PROCESSED / "robustness_cutoff_sweep_aggregate.csv",
        [
            "variant",
            "cutoff",
            "population",
            "positives",
            "base_rate",
            "xgboost_ap",
            "best_trivial_ap",
        ],
        [
            [
                r.variant,
                r.cutoff.isoformat(),
                r.population,
                r.positives,
                round(r.base_rate, 6),
                round(r.xgboost_ap, 6),
                round(r.best_trivial_ap, 6),
            ]
            for r in sweep_aggregate
        ],
    )
    _write_csv(
        PROCESSED / "robustness_cutoff_sweep_ranks.csv",
        ["variant", "substance", "cas", "cutoff", "rank", "population", "is_positive"],
        [
            [r.variant, r.name, r.cas, r.cutoff.isoformat(), r.rank, r.population, r.is_positive]
            for r in sweep_ranks
        ],
    )
    _write_csv(
        PROCESSED / "robustness_negative_controls.csv",
        [
            "variant",
            "cutoff",
            "group",
            "n_present",
            "in_top_10",
            "in_top_20",
            "in_top_50",
            "median_rank",
            "median_percentile",
        ],
        [
            [
                r.variant,
                r.cutoff.isoformat(),
                r.label,
                r.n_present,
                r.in_top_k.get(10, 0),
                r.in_top_k.get(20, 0),
                r.in_top_k.get(50, 0),
                "" if r.median_rank is None else round(r.median_rank, 1),
                "" if r.median_percentile is None else round(r.median_percentile, 4),
            ]
            for r in control_results
        ],
    )
    _write_csv(
        PROCESSED / "robustness_shap_funnel.csv",
        ["variant", "group", "mean_abs_shap", "share"],
        [
            [variant, r["group"], round(r["mean_abs_shap"], 6), round(r["share"], 6)]
            for variant, funnel_rows, _top in shap_results
            for r in funnel_rows
        ],
    )
    print(f"\nwrote robustness tables to {PROCESSED}")
    print(
        "  robustness_placebo.csv, robustness_cutoff_sweep_aggregate.csv, "
        "robustness_cutoff_sweep_ranks.csv, robustness_negative_controls.csv, "
        "robustness_shap_funnel.csv"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
