"""Export clean, Power-BI-ready tables from the pipeline's computed results.

Power BI is pointed at these tables, never at raw `data/processed/*.jsonl`
directly: those are pipeline-internal formats (one predicate per line, ids
not names, no risk scores). This script is the one place that joins graph,
sales, hazard, and eval data into tables shaped for a BI tool -- a substance
dimension with names and risk scores, a sales fact table, an events/timeline
fact table, and a flattened eval-results table for the methodology page.

Risk scores are the out-of-fold scores `ml/baseline.py` already computes
(`evaluate_cutoff`, the same headline/early-warning tabular model reported
in `V1_SCOPE.md`) -- not an in-sample refit. Presenting in-sample scores as
"predicted risk" would be optimistic in exactly the way the manifesto's
baseline rule exists to prevent; out-of-fold is the honest number.

Usage:
    python pipeline/11_export_powerbi.py
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pydantic import BaseModel

from hazium.graph.build import load_graph
from hazium.graph.store import TemporalGraph
from hazium.ml.baseline import evaluate_cutoff
from hazium.ml.dataset import DEFAULT_POSITIVE_KINDS, EARLY_WARNING_POSITIVE_KINDS, build_dataset
from hazium.ml.evaluate import summarize
from hazium.models import HazardClassification, RegulatoryEvent, SalesRecord, Substance
from hazium.resolve.ids import safe_substance_node_id
from hazium.resolve.names import SubstanceResolver, resolve_sales_records

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"
POWERBI = ROOT / "data" / "powerbi"

HEADLINE_CUTOFF = date(2023, 1, 1)
CUTOFFS = [date(2018, 1, 1), date(2020, 1, 1), date(2022, 1, 1), date(2023, 1, 1)]

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


def _cas_of(substance_id: str) -> str:
    prefix = "substance:cas:"
    return substance_id[len(prefix) :] if substance_id.startswith(prefix) else ""


def _name_of(graph: TemporalGraph, substance_id: str) -> str:
    return graph.node(substance_id).label if graph.has_node(substance_id) else substance_id


def export_dim_substance(
    graph: TemporalGraph,
    sales: list[SalesRecord],
    regevents: list[RegulatoryEvent],
    pesticide_ids: set[str],
) -> None:
    """One row per substance in the 2023 population, with both variants'
    out-of-fold risk scores and rank -- the Risk Explorer's backing table.
    """
    X, _y, ids = build_dataset(graph, sales, regevents, HEADLINE_CUTOFF)
    scores_by_variant: dict[str, dict[str, float]] = {}
    labels_by_variant: dict[str, dict[str, int]] = {}
    for variant, positive_kinds in VARIANTS:
        result = evaluate_cutoff(
            graph, sales, regevents, HEADLINE_CUTOFF, positive_kinds=positive_kinds
        )
        scores_by_variant[variant] = dict(zip(result.ids, result.scores["xgboost"], strict=True))
        labels_by_variant[variant] = dict(zip(result.ids, result.y_true.tolist(), strict=True))

    header = [
        "substance_id",
        "name",
        "cas_number",
        "is_pesticide",
        "clp_n_hazard_codes",
        "clp_has_cmr",
        "clp_has_aquatic_chronic_1",
        "clp_has_stot",
        "eu_has_approval",
        "eu_years_since_first_approval",
        "graph_metabolite_degree",
        "sales_latest_tonnage",
        "headline_risk_score",
        "headline_label",
        "early_warning_risk_score",
        "early_warning_label",
    ]
    rows = []
    for substance_id in ids:
        feature_row = X.loc[substance_id]
        rows.append(
            [
                substance_id,
                _name_of(graph, substance_id),
                _cas_of(substance_id),
                substance_id in pesticide_ids,
                feature_row["clp_n_hazard_codes"],
                bool(feature_row["clp_has_cmr"]),
                bool(feature_row["clp_has_aquatic_chronic_1"]),
                bool(feature_row["clp_has_stot"]),
                bool(feature_row["eu_has_approval"]),
                feature_row["eu_years_since_first_approval"],
                feature_row["graph_metabolite_degree"],
                feature_row["sales_latest_tonnage"],
                round(scores_by_variant["headline"][substance_id], 6),
                labels_by_variant["headline"][substance_id],
                round(scores_by_variant["early_warning"][substance_id], 6),
                labels_by_variant["early_warning"][substance_id],
            ]
        )
    _write_csv(POWERBI / "dim_substance.csv", header, rows)
    print(f"dim_substance: {len(rows)} rows")


def export_fact_sales(graph: TemporalGraph, sales: list[SalesRecord]) -> None:
    """One row per (substance, country, year).

    KEMI's annual sales reports each republish several trailing historical
    years, so the raw ``sales`` list legitimately contains the same
    (substance, country, year) more than once -- different report vintages
    restating the same figure, not conflicting values. ``ml/features.py``'s
    mean/latest-tonnage features are duplicate-invariant so this was never a
    problem there, but a BI tool's default ``SUM`` aggregation is not: it
    would double- or triple-count. Deduplicated here, keeping the most
    recently published (latest ``known_at``) restatement per year, so the
    export itself is safe to ``SUM`` in Power BI without a DAX workaround.
    """
    latest: dict[tuple[str, str, int], SalesRecord] = {}
    for record in sales:
        if not record.substance_id.startswith("substance:cas:"):
            continue
        key = (record.substance_id, record.country, record.year)
        if key not in latest or record.known_at > latest[key].known_at:
            latest[key] = record

    header = ["substance_id", "name", "country", "year", "tonnes_active_substance"]
    rows = [
        [
            record.substance_id,
            _name_of(graph, record.substance_id),
            record.country,
            record.year,
            record.tonnes_active_substance,
        ]
        for record in sorted(latest.values(), key=lambda r: (r.substance_id, r.country, r.year))
    ]
    _write_csv(POWERBI / "fact_sales.csv", header, rows)
    print(f"fact_sales: {len(rows)} rows (resolved to CAS, deduplicated by latest report)")


def export_fact_events(
    graph: TemporalGraph,
    classifications: list[HazardClassification],
    regevents: list[RegulatoryEvent],
) -> None:
    """A unified timeline: hazard classifications + regulatory events, one
    row per dated fact, for annotation overlays on the sales-trend chart.
    """
    header = ["substance_id", "name", "event_date", "event_type", "detail", "source"]
    rows = []
    for c in classifications:
        rows.append(
            [
                c.substance_id,
                _name_of(graph, c.substance_id),
                c.known_at.isoformat(),
                "hazard_classification",
                f"{c.hazard_code}" + (f" ({c.hazard_class})" if c.hazard_class else ""),
                c.source,
            ]
        )
    for e in regevents:
        rows.append(
            [
                e.substance_id,
                _name_of(graph, e.substance_id),
                e.event_date.isoformat(),
                e.kind.value,
                f"{e.jurisdiction}",
                e.source,
            ]
        )
    rows.sort(key=lambda r: r[2])
    _write_csv(POWERBI / "fact_events.csv", header, rows)
    print(f"fact_events: {len(rows)} rows")


def export_fact_eval_results(
    graph: TemporalGraph, sales: list[SalesRecord], regevents: list[RegulatoryEvent]
) -> None:
    """Flattened model-vs-trivial-baseline table, all cutoffs, both
    variants -- the Methodology page's backing table.
    """
    header = [
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
    rows = []
    for variant, positive_kinds in VARIANTS:
        for cutoff in CUTOFFS:
            result = evaluate_cutoff(graph, sales, regevents, cutoff, positive_kinds=positive_kinds)
            for row in summarize(result):
                rows.append(
                    [
                        variant,
                        row["cutoff"],
                        row["model"],
                        row["population"],
                        row["positives"],
                        round(row["average_precision"], 4),
                        round(row["ap_ci_lo"], 4),
                        round(row["ap_ci_hi"], 4),
                        round(row["precision_at_10"], 4),
                        round(row["precision_at_20"], 4),
                        round(row["precision_at_50"], 4),
                    ]
                )
    _write_csv(POWERBI / "fact_eval_results.csv", header, rows)
    print(f"fact_eval_results: {len(rows)} rows")


def _pesticide_ids(register_substances: list[Substance]) -> set[str]:
    return {
        safe_substance_node_id(cas_number=s.cas_number, name=s.name) for s in register_substances
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
    classifications = _load(PROCESSED / "clp_classifications.jsonl", HazardClassification)
    pesticide_ids = _pesticide_ids(register_substances)

    export_dim_substance(graph, sales, regevents, pesticide_ids)
    export_fact_sales(graph, sales)
    export_fact_events(graph, classifications, regevents)
    export_fact_eval_results(graph, sales, regevents)

    print(f"\nwrote Power BI export tables to {POWERBI}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
