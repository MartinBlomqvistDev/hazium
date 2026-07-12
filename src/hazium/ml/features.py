"""Pure feature functions over an ``as_of(T)`` graph view.

Every function here reads only facts already filtered to `known_at < T` (the
view itself for graph edges; explicit pre-filtering for sales and regulatory
events, which are not graph edges). This is what makes the feature set
temporally clean: nothing computed here can see the label event or anything
dated on or after the cutoff.

The five feature groups in ``V1_SCOPE.md`` describe the full aspiration; what
is implemented here is what is actually computable from ingested facts today.
Deferred (need the ``/details`` EU PPDB enrichment, not yet ingested — see
``TODO.md``): CLP M-factor, EU pesticide category, member-state authorisation
count, approval-extension count. Their absence is a scoping fact, not a bug:
adding them later only strengthens the feature set, never invalidates results
computed without them.
"""

from __future__ import annotations

import math
from datetime import date

from hazium.graph.store import TemporalGraph
from hazium.models import EdgeType, RegulatoryEvent, SalesRecord

# CLP severe hazard classes: CMR (carcinogen/mutagen/reprotoxic), the
# aquatic-chronic-1 tier, and STOT (specific target organ toxicity, repeated).
_CMR_CODES = frozenset(
    {
        "H340",
        "H350",
        "H350i",
        "H360",
        "H360F",
        "H360D",
        "H360FD",
        "H360Fd",
        "H360Df",
        "H361",
        "H361f",
        "H361d",
        "H361fd",
    }
)
_AQUATIC_CHRONIC_1_CODE = "H410"
_STOT_CODES = frozenset({"H370", "H372"})


def clp_features(view: TemporalGraph, substance_id: str, cutoff: date) -> dict[str, float]:
    """Hazard profile from ``CLASSIFIED_AS`` edges already in the view."""
    edges = [
        e
        for e in view.edges_of(substance_id)
        if e.predicate == EdgeType.CLASSIFIED_AS and e.subject == substance_id
    ]
    codes = {e.object for e in edges}  # hazard node ids, e.g. 'hazard:clp:H410'
    hazard_codes = {view.node(h).label for h in codes if view.has_node(h)}
    atps = {e.attrs["atp"] for e in edges if "atp" in e.attrs}
    known_ats = [e.known_at for e in edges]
    return {
        "clp_n_hazard_codes": float(len(hazard_codes)),
        "clp_n_distinct_atp": float(len(atps)),
        "clp_has_cmr": float(bool(hazard_codes & _CMR_CODES)),
        "clp_has_aquatic_chronic_1": float(_AQUATIC_CHRONIC_1_CODE in hazard_codes),
        "clp_has_stot": float(bool(hazard_codes & _STOT_CODES)),
        "clp_years_since_last_classification": _years_since(known_ats, cutoff),
    }


def efsa_features(view: TemporalGraph, substance_id: str, cutoff: date) -> dict[str, float]:
    """Assessment scrutiny from ``EVIDENCED_BY`` edges already in the view."""
    known_ats = [
        e.known_at
        for e in view.edges_of(substance_id)
        if e.predicate == EdgeType.EVIDENCED_BY and e.subject == substance_id
    ]
    span = (max(known_ats).year - min(known_ats).year) if known_ats else 0.0
    return {
        "efsa_n_assessments": float(len(known_ats)),
        "efsa_years_since_last": _years_since(known_ats, cutoff),
        "efsa_assessment_span_years": float(span),
    }


def sales_features(substance_id: str, sales: list[SalesRecord], cutoff: date) -> dict[str, float]:
    """Tonnage time-series features from pre-cutoff sales reports.

    Filters on ``known_at < cutoff`` (the report's publication date), not the
    data year, matching the graph's temporal discipline: what mattered is
    when the number was public, not which year it describes.
    """
    records = sorted(
        (r for r in sales if r.substance_id == substance_id and r.known_at < cutoff),
        key=lambda r: r.year,
    )
    if not records:
        return {
            "sales_latest_tonnage": 0.0,
            "sales_mean_tonnage": 0.0,
            "sales_trend_slope": 0.0,
            "sales_volatility": 0.0,
            "sales_years_on_market": 0.0,
            "sales_max_yoy_jump": 0.0,
        }
    tonnages = [r.tonnes_active_substance for r in records]
    years = [r.year for r in records]
    log_tonnages = [math.log1p(t) for t in tonnages]
    return {
        "sales_latest_tonnage": tonnages[-1],
        "sales_mean_tonnage": sum(tonnages) / len(tonnages),
        "sales_trend_slope": _slope(years, log_tonnages),
        "sales_volatility": _stdev(log_tonnages),
        "sales_years_on_market": float(len(set(years))),
        "sales_max_yoy_jump": _max_yoy_jump(tonnages),
    }


def graph_structural_features(view: TemporalGraph, substance_id: str) -> dict[str, float]:
    """Cheap structural signals: the bar a later GNN (V3) must beat.

    ``shared_hazard_substance_count`` walks each hazard the substance holds
    and counts distinct other substances sharing it, all within the view.

    ``graph_metabolite_degree`` counts pre-cutoff ``DEGRADES_TO`` neighbours
    in either direction (parent or metabolite) — the one genuine
    substance-substance structure in the graph (see V2_SCOPE.md). Added in
    V2a as the honest first move the baseline rule demands: if this hand-built
    degree feature already captures the signal a graph embedding (V2b) would
    also find, no embedding is needed.
    """
    edges = [
        e
        for e in view.edges_of(substance_id)
        if e.predicate in (EdgeType.CLASSIFIED_AS, EdgeType.EVIDENCED_BY)
        and e.subject == substance_id
    ]
    hazard_ids = {e.object for e in edges if e.predicate == EdgeType.CLASSIFIED_AS}
    neighbours: set[str] = set()
    for hazard_id in hazard_ids:
        for e in view.edges_of(hazard_id):
            if e.predicate == EdgeType.CLASSIFIED_AS and e.subject != substance_id:
                neighbours.add(e.subject)
    metabolite_neighbours = {
        e.object if e.subject == substance_id else e.subject
        for e in view.edges_of(substance_id)
        if e.predicate == EdgeType.DEGRADES_TO
    }
    return {
        "graph_degree": float(len(edges)),
        "graph_shared_hazard_substance_count": float(len(neighbours)),
        "graph_metabolite_degree": float(len(metabolite_neighbours)),
    }


def eu_regulatory_features(
    substance_id: str, regevents: list[RegulatoryEvent], cutoff: date
) -> dict[str, float]:
    """EU approval-history features from pre-cutoff regulatory events.

    Only ``APPROVAL`` events are used as features: a pre-cutoff
    ``NON_RENEWAL`` would mean the substance already lost approval before T,
    which ``build_dataset`` excludes from the population entirely (see its
    docstring), so no pre-cutoff non-renewal should ever reach here for a
    population member. Using it as a feature regardless would be leakage in
    spirit even where excluded in practice, so it is deliberately not read.
    """
    approvals = [
        e.known_at
        for e in regevents
        if e.substance_id == substance_id and e.kind.value == "approval" and e.known_at < cutoff
    ]
    return {
        "eu_has_approval": float(bool(approvals)),
        "eu_years_since_first_approval": (
            _years_since([min(approvals)], cutoff) if approvals else 0.0
        ),
    }


def _years_since(dates: list[date], cutoff: date) -> float:
    """Years between the latest of ``dates`` and ``cutoff`` — never today's date.

    Anchoring on ``cutoff`` (not ``date.today()``) keeps the feature
    reproducible and temporally honest: it must reflect what was knowable
    *at the cutoff*, not how long ago that is from whenever this runs.
    """
    if not dates:
        return 0.0
    return float(cutoff.year - max(dates).year)


def _slope(xs: list[int], ys: list[float]) -> float:
    """Ordinary least-squares slope; 0.0 for fewer than two points."""
    n = len(xs)
    if n < 2:
        return 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    den = sum((x - mean_x) ** 2 for x in xs)
    return num / den if den else 0.0


def _stdev(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    return math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))


def _max_yoy_jump(tonnages: list[float]) -> float:
    if len(tonnages) < 2:
        return 0.0
    jumps = []
    for prev, curr in zip(tonnages, tonnages[1:], strict=False):
        if prev == 0:
            continue
        jumps.append(abs(curr - prev) / prev)
    return max(jumps) if jumps else 0.0
