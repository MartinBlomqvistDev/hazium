"""Export the model's top-N riskiest substances at each annual cutoff.

Feeds the site's animated "risk over time" view: at every cutoff the full
population is scored (HEWB's headline model), and this dumps the top-N by
score with resolved names and, where applicable, the year the substance was
actually EU-non-renewed. A substance that is banned leaves the population at
its next cutoff (build_dataset censors already-realized non-renewals), so the
view shows substances rising, holding, and dropping out.

These are the model's risk *ranking*, not a list of banned substances: most
top-ranked actives were still approved. The ``banned_year`` field marks the
minority that a real EU action later confirmed.

Usage:
    python pipeline/18_export_rank_race.py
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from hazium.benchmark.hewb import ANNUAL_CUTOFFS
from hazium.graph.build import load_graph
from hazium.ml.baseline import rolling_origin_eval
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
P = ROOT / "data" / "processed"
TOP_N = 25


def _load(path: Path, model: type[BaseModel]) -> list:
    with path.open(encoding="utf-8") as f:
        return [model.model_validate_json(line) for line in f]


def main() -> int:
    graph = load_graph(P / "graph_nodes.jsonl", P / "graph_edges.jsonl")
    resolver = SubstanceResolver(_load(P / "kemi_register_substances.jsonl", Substance))
    sales = resolve_sales_records(_load(P / "kemi_sales.jsonl", SalesRecord), resolver)
    regevents = _load(P / "eu_ppdb_events.jsonl", RegulatoryEvent)
    rp = P / "kemi_reevaluations.jsonl"
    if rp.exists():
        regevents += _load(rp, RegulatoryEvent)
    lp = P / "literature_volume.jsonl"
    lit = _load(lp, LiteratureVolumeRecord) if lp.exists() else []
    clh_path = ROOT / "data" / "raw" / "clh_intentions_ppp.jsonl"
    clh = clh_intention_records(earliest_intention_year(clh_path)) if clh_path.exists() else []

    label: dict[str, str] = {}
    with (P / "graph_nodes.jsonl").open(encoding="utf-8") as f:
        for line in f:
            n = json.loads(line)
            if n.get("type") == "substance":
                label[n["id"]] = n["label"]

    banned: dict[str, int] = {}
    for e in regevents:
        if e.kind == RegulatoryEventKind.NON_RENEWAL:
            y = e.event_date.year
            if e.substance_id not in banned or y < banned[e.substance_id]:
                banned[e.substance_id] = y

    results = rolling_origin_eval(
        graph, sales, regevents, list(ANNUAL_CUTOFFS), lit_records=lit, clh_records=clh
    )

    per_year: dict[int, list[dict]] = {}
    for r in results:
        scores = r.scores["xgboost"]
        order = sorted(range(len(r.ids)), key=lambda i: -scores[i])[:TOP_N]
        rows = []
        for rank, i in enumerate(order, start=1):
            sid = r.ids[i]
            rows.append(
                {
                    "cas": sid.removeprefix("substance:cas:"),
                    "name": label.get(sid, sid),
                    "score": round(float(scores[i]), 4),
                    "rank": rank,
                    "banned_year": banned.get(sid),
                }
            )
        per_year[r.cutoff.year] = rows

    out = {"years": [c.year for c in ANNUAL_CUTOFFS], "top_n": TOP_N, "per_year": per_year}
    (ROOT / "web" / "data" / "rank_race.json").write_text(
        json.dumps(out, indent=1), encoding="utf-8"
    )
    sample = [x["name"] for x in per_year[min(per_year)][:3]]
    print(f"wrote {len(per_year)} years to web/data/rank_race.json; earliest-year top-3: {sample}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
