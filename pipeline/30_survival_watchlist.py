"""Score today's approved substances with the survival model.

`pipeline/13` ranks the current population using the binary "was it ever
withdrawn" target. That target is answered largely by approval age, so the
ranking it produces is substantially a list of old approvals. This replaces it
with the survival formulation, where age is the baseline hazard and the evidence
is what does the discriminating.

Two rules keep the training set honest.

**Only years whose horizon has fully elapsed are trained on.** A row from 2024
with a three-year horizon cannot be labelled until 2027, so including it would
mean training on outcomes that have not happened. Those rows are dropped rather
than counted as negatives, which is the same censoring rule the panel uses.

**Scoring happens at a cutoff of tomorrow.** Features are read exactly as they
are for any historical row, so every fact used is one that is public now, and
the ranking is reproducible from the archive at any later date.

Nothing here is verified. These are substances the model ranks as concerning,
and the approval expiry attached to each is the date the claim becomes
checkable.

Usage:
    python pipeline/30_survival_watchlist.py
    python pipeline/30_survival_watchlist.py --horizon 1 --top 200
"""

from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from hazium.benchmark.survival import (
    EVENT,
    YEAR,
    PanelSpec,
    build_panel,
    feature_columns,
    first_event_dates,
)
from hazium.graph.build import load_graph
from hazium.ml.baseline import make_model
from hazium.ml.dataset import build_dataset
from hazium.models import (
    LiteratureVolumeRecord,
    RegulatoryEvent,
    RegulatoryEventKind,
    SalesRecord,
    Substance,
)
from hazium.resolve.names import SubstanceResolver, resolve_sales_records

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"

#: Default outcome window. Three years suits a watchlist better than one: it
#: carries three times the training events at a comparable benefit (+0.119
#: against +0.141 at one year), and it matches the horizon a reader cares about.
DEFAULT_HORIZON = 3


def _load(path: Path, model):
    with path.open(encoding="utf-8") as f:
        return [model.model_validate_json(line) for line in f]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--horizon", type=int, default=DEFAULT_HORIZON)
    parser.add_argument("--top", type=int, default=100)
    args = parser.parse_args()

    today = date.today()
    graph = load_graph(PROCESSED / "graph_nodes.jsonl", PROCESSED / "graph_edges.jsonl")
    sales = resolve_sales_records(
        _load(PROCESSED / "kemi_sales.jsonl", SalesRecord),
        SubstanceResolver(_load(PROCESSED / "kemi_register_substances.jsonl", Substance)),
    )
    events = _load(PROCESSED / "eu_ppdb_events.jsonl", RegulatoryEvent)
    lit = _load(PROCESSED / "literature_volume.jsonl", LiteratureVolumeRecord)

    panel = build_panel(graph, sales, events, lit, PanelSpec(horizon_years=args.horizon))
    # A row is only labellable once its whole horizon lies in the past.
    complete = panel[YEAR] + args.horizon <= today.year
    train = panel[complete]
    print(
        f"panel {len(panel):,} rows; trainable {len(train):,} "
        f"(years through {int(train[YEAR].max())}), {int(train[EVENT].sum())} events, "
        f"horizon {args.horizon}y"
    )

    columns = feature_columns()
    model = make_model(train[EVENT], 42)
    model.fit(train[columns], train[EVENT])

    # Score today's at-risk set: approved, not already withdrawn.
    features, _label, ids = build_dataset(
        graph, sales, events, today + timedelta(days=1), lit_records=lit
    )
    approved = features["eu_has_approval"].to_numpy() > 0
    withdrawal = first_event_dates(events, RegulatoryEventKind.NON_RENEWAL)
    at_risk = [keep and withdrawal.get(sid) is None for sid, keep in zip(ids, approved)]
    scoring = features[at_risk]
    scoring_ids = [sid for sid, keep in zip(ids, at_risk) if keep]
    scores = model.predict_proba(scoring[columns])[:, 1]
    print(f"scoring {len(scoring_ids)} approved substances still at risk")

    # Column names match pipeline/13's output so the crop-exposure, resolution
    # and site exporters can read either without knowing which produced it.
    in_sweden = {
        f"substance:cas:{s.cas_number.strip()}"
        for s in _load(PROCESSED / "kemi_register_substances.jsonl", Substance)
        if s.cas_number
    }
    order = np.argsort(-scores)
    out = PROCESSED / f"survival_watchlist_h{args.horizon}.csv"
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "rank",
                "substance_id",
                "name",
                "score",
                "eu_approved_pesticide",
                "in_kemi_sweden_register",
                "years_since_eu_approval",
            ]
        )
        for rank, i in enumerate(order, start=1):
            sid = scoring_ids[i]
            node = graph.node(sid) if sid in graph._nodes else None
            writer.writerow(
                [
                    rank,
                    sid,
                    node.label if node else sid,
                    f"{scores[i]:.6f}",
                    True,
                    sid in in_sweden,
                    int(scoring.iloc[i]["eu_years_since_first_approval"]),
                ]
            )

    print(f"\ntop {min(args.top, 15)} by modelled {args.horizon}-year hazard:")
    print(f"  {'rank':>4} {'substance':<38} {'p':>8} {'approved':>9}")
    print("  " + "-" * 62)
    for rank, i in enumerate(order[:15], start=1):
        sid = scoring_ids[i]
        node = graph.node(sid) if sid in graph._nodes else None
        label = (node.label if node else sid)[:38]
        print(
            f"  {rank:>4} {label:<38} {scores[i]:>8.4f} "
            f"{int(scoring.iloc[i]['eu_years_since_first_approval']):>7}y"
        )
    print(f"\nwrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
