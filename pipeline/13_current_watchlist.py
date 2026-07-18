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
from hazium.ml.dataset import DEFAULT_POSITIVE_KINDS, EARLY_WARNING_POSITIVE_KINDS, build_dataset
from hazium.models import RegulatoryEvent, SalesRecord, Substance
from hazium.resolve.ids import safe_substance_node_id
from hazium.resolve.names import SubstanceResolver, resolve_sales_records

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"

TRAIN_CUTOFF = date(2024, 1, 1)
TOP_N = 30
EXPLAIN_TOP = 3

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


def _pesticide_ids(register_substances: list[Substance]) -> set[str]:
    return {
        safe_substance_node_id(cas_number=s.cas_number, name=s.name) for s in register_substances
    }


def _name_of(graph: TemporalGraph, substance_id: str) -> str:
    return graph.node(substance_id).label if graph.has_node(substance_id) else substance_id


def build_watchlist(graph, sales, regevents, positive_kinds, top_n=TOP_N):
    """Train on TRAIN_CUTOFF (complete, real labels by now); score today.

    Returns ``None`` if there are too few training positives. Otherwise
    ``(ranked_rows, explainer, X_now, ids_now)`` -- the explainer is built
    from the *trained* model, ready to explain any row of ``X_now``.
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
    top = ranked[:top_n]

    explainer = shap.TreeExplainer(model)
    return top, explainer, X_now, ids_now


def main() -> int:
    graph = load_graph(PROCESSED / "graph_nodes.jsonl", PROCESSED / "graph_edges.jsonl")
    register_substances = _load(PROCESSED / "kemi_register_substances.jsonl", Substance)
    resolver = SubstanceResolver(register_substances)
    sales = resolve_sales_records(_load(PROCESSED / "kemi_sales.jsonl", SalesRecord), resolver)
    regevents = _load(PROCESSED / "eu_ppdb_events.jsonl", RegulatoryEvent)
    kemi_reeval_path = PROCESSED / "kemi_reevaluations.jsonl"
    if kemi_reeval_path.exists():
        regevents += _load(kemi_reeval_path, RegulatoryEvent)
    pesticide_ids = _pesticide_ids(register_substances)

    print(f"Trained on {TRAIN_CUTOFF} (complete, materialised outcomes as of today).")
    print(f"Scored on today's features ({date.today()}).")
    print(
        "\nThese are UNVERIFIED forward-looking scores, not a validated result -- "
        "nothing here has been checked against reality, because it can't be yet.\n"
    )

    for variant, positive_kinds in VARIANTS:
        result = build_watchlist(graph, sales, regevents, positive_kinds)
        if result is None:
            print(f"[{variant}] skipped: too few positives in training data")
            continue
        top, explainer, X_now, ids_now = result

        rows = []
        for rank, (sid, score) in enumerate(top, start=1):
            rows.append(
                {
                    "rank": rank,
                    "substance_id": sid,
                    "name": _name_of(graph, sid),
                    "score": round(float(score), 6),
                    "is_pesticide": sid in pesticide_ids,
                }
            )

        print(f"\n=== [{variant}] current watchlist, top {len(rows)} ===")
        print(f"{'rank':>4s}  {'score':>8s}  {'pesticide?':>10s}  name")
        for r in rows:
            print(
                f"{r['rank']:>4d}  {r['score']:>8.4f}  {str(r['is_pesticide']):>10s}  {r['name']}"
            )

        _write_csv(
            PROCESSED / f"current_watchlist_{variant}.csv",
            ["rank", "substance_id", "name", "score", "is_pesticide"],
            [
                [r["rank"], r["substance_id"], r["name"], r["score"], r["is_pesticide"]]
                for r in rows
            ],
        )

        print(f"\n  --- why the top {EXPLAIN_TOP} rank highly (today's features) ---")
        top_ids = [r["substance_id"] for r in rows[:EXPLAIN_TOP]]
        shap_values = explainer(X_now.loc[top_ids])
        for i, r in enumerate(rows[:EXPLAIN_TOP]):
            print(f"  {r['name']}:")
            contributions = sorted(
                zip(X_now.columns, shap_values.values[i], strict=True),
                key=lambda pair: -pair[1],
            )
            for fname, val in contributions[:4]:
                print(f"    {fname}: {val:+.4f}")

    print(f"\nwrote current_watchlist_{{headline,early_warning}}.csv to {PROCESSED}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
