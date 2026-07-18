"""Score the *current* population: what does the model think is concerning
right now, among substances that have not (yet) faced a regulatory action?

Everything else in this repo is retrospective -- V1, V2, and HEWB all ask
"would the model have flagged a *known, already-realized* outcome." This
script asks a genuinely different, forward-looking question, and the answer
carries a different epistemic status: **these are unverified until the
future actually happens.** Nothing here has been checked against reality yet,
because it can't be -- that is the whole point of a watchlist. Report it as
"the model currently ranks these as concerning," never as "Hazium predicts
X will be banned."

Method: train on the most recent cutoff with real, materialised outcomes
(2024-01-01 -- everything that has happened since is now known, so its
labels are complete, not still pending), fit *in-sample* on the full training
population (this is a deploy step, not an evaluation -- out-of-fold exists to
report honest metrics, and there is no metric to report here, only a score to
act on). Then score today's population using today's features -- built the
same way, but at a cutoff of "tomorrow" so every currently-known fact is
included. Substances already realized (already banned) by today are excluded
from the scoring population by `build_dataset`'s own censoring rule, exactly
as intended.

Explanation reuses the *training*-fitted model's SHAP explainer against
*today's* feature values (not `explain/shap_baseline.py`'s `fit_and_explain`,
which fits and explains the same data -- here training data and scoring data
are deliberately different populations, so the explainer is built once from
the trained model and applied to the current data directly).

Two corrections over the first pass, both real bugs, not polish:

1. **Pesticide labelling.** `is_pesticide` was wrongly defined as "in KEMI's
   Swedish register" -- several genuine EU-approved pesticide active
   substances (Propoxycarbazone, Cyhalofop-butyl) were mislabelled `False`
   just because they aren't marketed in Sweden specifically. Fixed: a
   substance is flagged a pesticide if it has ``eu_has_approval`` set --
   membership in the EU *Pesticides* Database's approval events is a direct,
   correct test, not a proxy. `in_kemi_sweden_register` is kept as a
   separate, honestly-named column for readers who specifically want
   Swedish-market presence.
2. **Time dominance.** `eu_years_since_first_approval` swamped every other
   feature in the global ranking (5-10x the next-largest SHAP contribution),
   making the list read as "oldest first" rather than a differentiated risk
   read -- true, and not very informative on its own. Mitigated by
   **cohort-relative ranking**: bucket substances by approval-age band, then
   rank within each band. This does not discard the age signal (HEWB
   repeatedly showed it is genuinely predictive) or require retraining; it
   answers a sharper question -- "of substances that have been around
   roughly this long, which one looks worst" -- which is what actually
   surfaces something non-obvious.

Usage:
    python pipeline/13_current_watchlist.py
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import shap
from pydantic import BaseModel

from hazium.graph.build import load_graph
from hazium.graph.store import TemporalGraph
from hazium.ml.baseline import make_model
from hazium.ml.dataset import (
    DEFAULT_POSITIVE_KINDS,
    EARLY_WARNING_POSITIVE_KINDS,
    approval_age_non_renewal_rates,
    build_dataset,
)
from hazium.models import RegulatoryEvent, SalesRecord, Substance
from hazium.resolve.ids import safe_substance_node_id
from hazium.resolve.names import SubstanceResolver, resolve_sales_records

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"

TRAIN_CUTOFF = date(2024, 1, 1)
TOP_N = 30
TOP_N_PER_COHORT = 5
EXPLAIN_TOP = 3

#: Approval-age bands in years, half-open [lo, hi). Chosen to split the
#: observed range (roughly 0-30+ years) into a handful of readable groups,
#: not derived from any statistical criterion -- revisit if the population's
#: age distribution shifts materially.
AGE_COHORTS: tuple[tuple[str, float, float], ...] = (
    ("0-9 years approved", 0, 10),
    ("10-19 years approved", 10, 20),
    ("20-29 years approved", 20, 30),
    ("30+ years approved", 30, float("inf")),
)

VARIANTS = (
    ("headline", DEFAULT_POSITIVE_KINDS),
    ("early_warning", EARLY_WARNING_POSITIVE_KINDS),
)


def _load(path: Path, model: type[BaseModel]) -> list:
    with path.open(encoding="utf-8") as f:
        return [model.model_validate_json(line) for line in f]


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


def _kemi_register_ids(register_substances: list[Substance]) -> set[str]:
    """Swedish-market presence only -- NOT a general pesticide test.

    Kept distinct from ``eu_has_approval`` deliberately: a substance can be a
    real, EU-approved pesticide without being marketed in Sweden, and this
    column exists so that distinction stays visible rather than collapsed
    into one ambiguous flag.
    """
    return {
        safe_substance_node_id(cas_number=s.cas_number, name=s.name) for s in register_substances
    }


def _name_of(graph: TemporalGraph, substance_id: str) -> str:
    return graph.node(substance_id).label if graph.has_node(substance_id) else substance_id


def build_watchlist(graph, sales, regevents, positive_kinds):
    """Train on TRAIN_CUTOFF (complete, real labels by now); score today.

    Returns ``None`` if there are too few training positives. Otherwise
    ``(ranked, explainer, X_now)`` where ``ranked`` is the *full* population,
    sorted best-first, as ``(substance_id, score)`` pairs -- not truncated
    here, so callers can build both the global top-N and cohort-relative
    views from the same scoring pass.
    """
    X_train, y_train, _train_ids = build_dataset(
        graph, sales, regevents, TRAIN_CUTOFF, positive_kinds
    )
    if y_train.sum() < 2:
        return None
    model = make_model(y_train)
    model.fit(X_train, y_train)

    scoring_cutoff = date.today() + timedelta(days=1)
    X_now, _y_now, ids_now = build_dataset(graph, sales, regevents, scoring_cutoff, positive_kinds)

    scores = model.predict_proba(X_now)[:, 1]
    ranked = sorted(zip(ids_now, scores, strict=True), key=lambda pair: -pair[1])

    explainer = shap.TreeExplainer(model)
    return ranked, explainer, X_now


def _row_dict(graph, sid, score, rank, X_now, kemi_ids) -> dict:
    feature_row = X_now.loc[sid]
    return {
        "rank": rank,
        "substance_id": sid,
        "name": _name_of(graph, sid),
        "score": round(float(score), 6),
        "eu_approved_pesticide": bool(feature_row["eu_has_approval"]),
        "in_kemi_sweden_register": sid in kemi_ids,
        "years_since_eu_approval": feature_row["eu_years_since_first_approval"],
    }


def _explain(explainer, X_now, rows: list[dict]) -> None:
    if not rows:
        return
    ids = [r["substance_id"] for r in rows]
    shap_values = explainer(X_now.loc[ids])
    for i, r in enumerate(rows):
        print(f"  {r['name']} (global rank {r['rank']}):")
        contributions = sorted(
            zip(X_now.columns, shap_values.values[i], strict=True), key=lambda pair: -pair[1]
        )
        for fname, val in contributions[:4]:
            print(f"    {fname}: {val:+.4f}")


def main() -> int:
    graph = load_graph(PROCESSED / "graph_nodes.jsonl", PROCESSED / "graph_edges.jsonl")
    register_substances = _load(PROCESSED / "kemi_register_substances.jsonl", Substance)
    resolver = SubstanceResolver(register_substances)
    sales = resolve_sales_records(_load(PROCESSED / "kemi_sales.jsonl", SalesRecord), resolver)
    regevents = _load(PROCESSED / "eu_ppdb_events.jsonl", RegulatoryEvent)
    kemi_reeval_path = PROCESSED / "kemi_reevaluations.jsonl"
    if kemi_reeval_path.exists():
        regevents += _load(kemi_reeval_path, RegulatoryEvent)
    kemi_ids = _kemi_register_ids(register_substances)

    print(f"Trained on {TRAIN_CUTOFF} (complete, materialised outcomes as of today).")
    print(f"Scored on today's features ({date.today()}).")
    print(
        "\nThese are UNVERIFIED forward-looking scores, not a validated result -- "
        "nothing here has been checked against reality, because it can't be yet.\n"
    )

    print("=== Approval-age vs. non-renewal rate (all EU PPDB events, unfiltered) ===")
    print(
        "Read this BEFORE the cohort breakdown below: an empty/thin band there means\n"
        "'no substances that old exist in the data' (the EU approval framework itself\n"
        "only dates to the early-to-mid 1990s), NOT 'everything that old was banned'.\n"
        "'Non-renewed' also isn't a synonym for 'deemed toxic' -- EU PPDB records that\n"
        "a non-renewal happened and when, not why; this data can't rule out\n"
        "commercial or administrative reasons.\n"
    )
    age_rows = approval_age_non_renewal_rates(regevents, date.today())
    print(f"{'band':10s} {'total':>7s} {'non-renewed':>13s} {'still active':>13s} {'rate':>7s}")
    for r in age_rows:
        rate_str = f"{r['non_renewal_rate']:.1%}" if r["non_renewal_rate"] is not None else "n/a"
        print(
            f"{r['age_band']:10s} {r['total']:7d} {r['non_renewed']:13d} "
            f"{r['still_active']:13d} {rate_str:>7s}"
        )
    _write_csv(
        PROCESSED / "approval_age_non_renewal_rates.csv",
        ["age_band", "total", "non_renewed", "still_active", "non_renewal_rate"],
        [
            [r["age_band"], r["total"], r["non_renewed"], r["still_active"], r["non_renewal_rate"]]
            for r in age_rows
        ],
    )

    for variant, positive_kinds in VARIANTS:
        result = build_watchlist(graph, sales, regevents, positive_kinds)
        if result is None:
            print(f"[{variant}] skipped: too few positives in training data")
            continue
        ranked, explainer, X_now = result

        all_rows = [
            _row_dict(graph, sid, score, rank, X_now, kemi_ids)
            for rank, (sid, score) in enumerate(ranked, start=1)
        ]
        top_rows = all_rows[:TOP_N]

        print(f"\n=== [{variant}] GLOBAL top {len(top_rows)} ===")
        print(f"{'rank':>4s}  {'score':>8s}  {'EU pesticide?':>13s}  name")
        for r in top_rows:
            print(
                f"{r['rank']:>4d}  {r['score']:>8.4f}  "
                f"{str(r['eu_approved_pesticide']):>13s}  {r['name']}"
            )

        _write_csv(
            PROCESSED / f"current_watchlist_{variant}.csv",
            [
                "rank",
                "substance_id",
                "name",
                "score",
                "eu_approved_pesticide",
                "in_kemi_sweden_register",
                "years_since_eu_approval",
            ],
            [
                [
                    r["rank"],
                    r["substance_id"],
                    r["name"],
                    r["score"],
                    r["eu_approved_pesticide"],
                    r["in_kemi_sweden_register"],
                    r["years_since_eu_approval"],
                ]
                for r in all_rows
            ],
        )

        print(
            f"\n=== [{variant}] COHORT-RELATIVE: top {TOP_N_PER_COHORT} per approval-age band ==="
        )
        print(
            "(counts below are the STILL-ACTIVE population only -- see the unfiltered "
            "approval-age table printed above for the true total including non-renewed "
            "substances; an empty band here does not mean '0 substances ever approved that "
            "old', it can also mean 'all of them were already non-renewed'.)"
        )
        cohort_rows: list[dict] = []
        for label, lo, hi in AGE_COHORTS:
            band = [r for r in all_rows if lo <= r["years_since_eu_approval"] < hi]
            band_top = band[:TOP_N_PER_COHORT]  # all_rows is already globally sorted
            print(f"\n  [{label}] ({len(band)} substances in this band)")
            for local_rank, r in enumerate(band_top, start=1):
                print(
                    f"    {local_rank}. {r['name']}  (global rank {r['rank']}, score {r['score']:.4f})"
                )
                cohort_rows.append({**r, "cohort": label, "rank_in_cohort": local_rank})

        _write_csv(
            PROCESSED / f"current_watchlist_{variant}_by_cohort.csv",
            ["cohort", "rank_in_cohort", "rank", "substance_id", "name", "score"],
            [
                [
                    r["cohort"],
                    r["rank_in_cohort"],
                    r["rank"],
                    r["substance_id"],
                    r["name"],
                    r["score"],
                ]
                for r in cohort_rows
            ],
        )

        print(f"\n  --- why the GLOBAL top {EXPLAIN_TOP} rank highly (today's features) ---")
        _explain(explainer, X_now, top_rows[:EXPLAIN_TOP])

    print(f"\nwrote current_watchlist_{{headline,early_warning}}[_by_cohort].csv to {PROCESSED}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
