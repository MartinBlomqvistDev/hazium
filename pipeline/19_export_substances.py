"""Export the full scored population as a compact JSON for the site's
substance explorer.

Unlike ``pipeline/11`` (Power BI, and predating Tier 1/2 so its scores are
stale), this regenerates the out-of-fold ranking with the *current* feature
set — literature (Tier 1) and CLH intentions (Tier 2) included — at the HEWB
headline cutoff, exactly as ``pipeline/12`` runs the benchmark. Both label
variants are exported so the explorer can toggle between them.

The scores are the honest out-of-fold ones (``evaluate_cutoff``), never an
in-sample refit: the explorer shows how the model *ranked* substances at a
fixed past cutoff using only prior evidence, which is a ranking, not a
prediction of the future. That framing is carried in the payload ``note`` and
must be surfaced in the UI (see the current-watchlist UNVERIFIED discipline).

Re-run and commit ``web/data/substances.json`` after any change that moves the
scores (a new feature, a HEWB version bump).

Usage:
    python pipeline/19_export_substances.py
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from pydantic import BaseModel

from hazium.benchmark.hewb import HEWB_VERSION, LANDMARK_CASES
from hazium.graph.build import load_graph
from hazium.graph.store import TemporalGraph
from hazium.ml.baseline import evaluate_cutoff
from hazium.ml.dataset import DEFAULT_POSITIVE_KINDS, EARLY_WARNING_POSITIVE_KINDS, build_dataset
from hazium.models import (
    CLHIntentionRecord,
    LiteratureVolumeRecord,
    RegulatoryEvent,
    SalesRecord,
    Substance,
)
from hazium.resolve.ids import safe_substance_node_id
from hazium.resolve.names import SubstanceResolver, resolve_sales_records
from hazium.sources.echa_clh import clh_intention_records, earliest_intention_year

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"
SITE_DATA = ROOT / "web" / "data" / "substances.json"

#: The HEWB headline cutoff — the same fixed origin the aggregate AP is quoted
#: at, so a reader who finds a landmark in the explorer sees the rank that the
#: benchmark and the fluazinam story are told against.
CUTOFF = date(2023, 1, 1)

VARIANTS = (
    ("headline", DEFAULT_POSITIVE_KINDS),
    ("early_warning", EARLY_WARNING_POSITIVE_KINDS),
)


def _load(path: Path, model: type[BaseModel]) -> list:
    with path.open(encoding="utf-8") as f:
        return [model.model_validate_json(line) for line in f]


def _load_literature(path: Path) -> list[LiteratureVolumeRecord]:
    return _load(path, LiteratureVolumeRecord) if path.exists() else []


def _load_clh() -> list[CLHIntentionRecord]:
    snapshot = ROOT / "data" / "raw" / "clh_intentions_ppp.jsonl"
    return clh_intention_records(earliest_intention_year(snapshot)) if snapshot.exists() else []


def _cas_of(substance_id: str) -> str:
    prefix = "substance:cas:"
    return substance_id[len(prefix) :] if substance_id.startswith(prefix) else ""


def _ranks(scores: dict[str, float]) -> dict[str, int]:
    """1-indexed ranks, highest score first, ties broken stably by id order —
    the same rule ``benchmark/hewb.rank_of`` uses, so ranks are consistent."""
    order = sorted(scores, key=lambda sid: (-scores[sid], sid))
    return {sid: i for i, sid in enumerate(order, start=1)}


def build_payload(
    graph: TemporalGraph,
    sales: list[SalesRecord],
    regevents: list[RegulatoryEvent],
    pesticide_ids: set[str],
    lit_records: list[LiteratureVolumeRecord],
    clh_records: list[CLHIntentionRecord],
) -> dict:
    X, _y, ids = build_dataset(
        graph, sales, regevents, CUTOFF, DEFAULT_POSITIVE_KINDS, lit_records, clh_records
    )

    scores: dict[str, dict[str, float]] = {}
    labels: dict[str, dict[str, int]] = {}
    ranks: dict[str, dict[str, int]] = {}
    for variant, positive_kinds in VARIANTS:
        result = evaluate_cutoff(
            graph,
            sales,
            regevents,
            CUTOFF,
            positive_kinds=positive_kinds,
            lit_records=lit_records,
            clh_records=clh_records,
        )
        s = dict(zip(result.ids, result.scores["xgboost"], strict=True))
        scores[variant] = s
        labels[variant] = dict(zip(result.ids, result.y_true.tolist(), strict=True))
        ranks[variant] = _ranks(s)

    landmark_by_cas = {c.cas: c.name for c in LANDMARK_CASES}

    substances = []
    for sid in ids:
        row = X.loc[sid]
        cas = _cas_of(sid)
        entry = {
            "n": graph.node(sid).label if graph.has_node(sid) else sid,
            "c": cas,
            "p": int(sid in pesticide_ids),
            "hz": int(row["clp_n_hazard_codes"]),
            "cmr": int(bool(row["clp_has_cmr"])),
            "aq": int(bool(row["clp_has_aquatic_chronic_1"])),
            "st": int(bool(row["clp_has_stot"])),
            "ap": int(bool(row["eu_has_approval"])),
            "ag": round(float(row["eu_years_since_first_approval"]), 1),
            "sl": round(float(row["sales_latest_tonnage"]), 2),
            "hr": ranks["headline"][sid],
            "hL": labels["headline"][sid],
            "er": ranks["early_warning"][sid],
            "eL": labels["early_warning"][sid],
        }
        if cas in landmark_by_cas:
            entry["lm"] = landmark_by_cas[cas]
        substances.append(entry)

    substances.sort(key=lambda e: e["hr"])

    return {
        "cutoff": CUTOFF.isoformat(),
        "hewb_version": HEWB_VERSION,
        "population": len(substances),
        "headline_positives": sum(1 for e in substances if e["hL"] == 1),
        "early_warning_positives": sum(1 for e in substances if e["eL"] == 1),
        "note": (
            "The model's out-of-fold risk ranking of every substance in the "
            "population at the 2023-01-01 cutoff, using only evidence dated "
            "before it. This is a ranking of past evidence, not a prediction "
            "of future bans."
        ),
        "substances": substances,
    }


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
    clh_records = _load_clh()
    pesticide_ids = {
        safe_substance_node_id(cas_number=s.cas_number, name=s.name) for s in register_substances
    }
    print(f"literature records: {len(lit_records)} | CLH records: {len(clh_records)}")

    payload = build_payload(graph, sales, regevents, pesticide_ids, lit_records, clh_records)

    SITE_DATA.parent.mkdir(parents=True, exist_ok=True)
    SITE_DATA.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    kb = SITE_DATA.stat().st_size / 1024
    print(
        f"wrote {SITE_DATA} ({payload['population']} substances, "
        f"{payload['headline_positives']}/{payload['early_warning_positives']} positives, {kb:.0f} KB)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
