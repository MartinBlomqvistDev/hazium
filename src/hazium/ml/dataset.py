"""Assemble the temporally-clean feature matrix and label for one cutoff.

``build_dataset`` is the single seam between the graph/facts and the model:
everything upstream is Pydantic facts and a ``TemporalGraph``; everything
downstream is a plain ``pandas.DataFrame``. Pure given its inputs — no I/O,
no randomness — so it is fully unit-testable against hand-built graphs.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from hazium.graph.store import TemporalGraph
from hazium.ml.features import (
    clp_features,
    efsa_features,
    eu_regulatory_features,
    graph_structural_features,
    sales_features,
)
from hazium.models import NodeType, RegulatoryEvent, RegulatoryEventKind, SalesRecord

FEATURE_COLUMNS = [
    "clp_n_hazard_codes",
    "clp_n_distinct_atp",
    "clp_has_cmr",
    "clp_has_aquatic_chronic_1",
    "clp_has_stot",
    "clp_years_since_last_classification",
    "efsa_n_assessments",
    "efsa_years_since_last",
    "efsa_assessment_span_years",
    "sales_latest_tonnage",
    "sales_mean_tonnage",
    "sales_trend_slope",
    "sales_volatility",
    "sales_years_on_market",
    "sales_max_yoy_jump",
    "graph_degree",
    "graph_shared_hazard_substance_count",
    "graph_metabolite_degree",
    "eu_has_approval",
    "eu_years_since_first_approval",
]


DEFAULT_POSITIVE_KINDS = frozenset({RegulatoryEventKind.NON_RENEWAL})

#: Broadened label variant: also counts a Swedish national reevaluation as a
#: positive, not just a completed EU non-renewal. A materially weaker,
#: earlier signal (a review starting doesn't mean it will end in withdrawal),
#: reported as a distinct secondary variant, never silently merged into the
#: headline result. See the 2026-07-12 DEV_LOG entry ("KEMI reevaluation
#: announcements") for why this exists and its caveats (all positives it adds
#: beyond ``DEFAULT_POSITIVE_KINDS`` currently trace to a single announcement,
#: not independent evidence).
EARLY_WARNING_POSITIVE_KINDS = frozenset(
    {RegulatoryEventKind.NON_RENEWAL, RegulatoryEventKind.REEVALUATION_STARTED}
)


def build_dataset(
    graph: TemporalGraph,
    sales: list[SalesRecord],
    regevents: list[RegulatoryEvent],
    cutoff: date,
    positive_kinds: frozenset[RegulatoryEventKind] = DEFAULT_POSITIVE_KINDS,
) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    """Build (X, y, substance_ids) for one rolling-origin cutoff.

    Population: substances present in ``graph.as_of(cutoff)`` (≥1 dated
    pre-cutoff fact), **excluding** any substance that already has a
    label-defining event (``positive_kinds``) dated before the cutoff. A
    substance whose fate is already decided as of T is not a member of the
    "at risk of a future event" population going forward — including it
    would either double-count an already-realized event or degenerate into a
    permanent, uninformative negative. This censoring rule is not explicit in
    ``V1_SCOPE.md``'s task section but follows directly from what "future
    regulatory action" means; documented here since it is not obvious from
    the label definition alone.

    Label: 1 iff the substance has an event whose ``kind`` is in
    ``positive_kinds``, dated `>= cutoff`. Defaults to EU non-renewal only
    (V1's headline label); pass ``EARLY_WARNING_POSITIVE_KINDS`` for the
    broadened secondary variant.
    """
    view = graph.as_of(cutoff)
    already_realized = {
        e.substance_id for e in regevents if e.kind in positive_kinds and e.event_date < cutoff
    }
    population = [
        n.id for n in view.nodes() if n.type == NodeType.SUBSTANCE and n.id not in already_realized
    ]

    future_positives = {
        e.substance_id for e in regevents if e.kind in positive_kinds and e.event_date >= cutoff
    }

    rows = []
    for substance_id in population:
        row: dict[str, float] = {}
        row.update(clp_features(view, substance_id, cutoff))
        row.update(efsa_features(view, substance_id, cutoff))
        row.update(sales_features(substance_id, sales, cutoff))
        row.update(graph_structural_features(view, substance_id))
        row.update(eu_regulatory_features(substance_id, regevents, cutoff))
        rows.append(row)

    X = pd.DataFrame(rows, columns=FEATURE_COLUMNS, index=population)
    y = pd.Series(
        [1 if sid in future_positives else 0 for sid in population],
        index=population,
        name="label",
    )
    return X, y, population


#: Approval-age bands in years, half-open [lo, hi). Matches
#: ``pipeline/13_current_watchlist.py``'s cohort bands; kept here so the two
#: stay in sync rather than duplicating the boundaries in two places.
APPROVAL_AGE_BANDS: tuple[tuple[str, float, float], ...] = (
    ("0-9", 0, 10),
    ("10-19", 10, 20),
    ("20-29", 20, 30),
    ("30+", 30, float("inf")),
)


def approval_age_non_renewal_rates(
    regevents: list[RegulatoryEvent],
    today: date,
    bands: tuple[tuple[str, float, float], ...] = APPROVAL_AGE_BANDS,
) -> list[dict]:
    """Real non-renewal rate by EU approval-age band, direct from EU PPDB
    events, with no population filtering.

    Exists specifically to prevent a real misreading found in practice: a
    *population-filtered* view (e.g. the current watchlist, which excludes
    already-non-renewed substances by construction) can show an empty or
    thin oldest age band, which looks like "everything that old was banned."
    This function counts from the raw approval/non-renewal events
    themselves, so ``total`` is the true denominator — non-renewed
    substances included, not just the survivors.

    Verified 2026-07-18: with ``today`` in 2026, the oldest band (30+ years
    since a substance's earliest EU approval) has zero substances at all,
    non-renewed or not. That is a ceiling of the modern EU pesticide
    approval framework itself (Directive 91/414/EEC, early-to-mid 1990s): no
    approval event *can* be dated further back than the framework's own
    start. It is not evidence that "all 30+-year-old substances were deemed
    toxic" — there are none in the data to judge either way.

    Also worth stating plainly, and not something this function can fix:
    "non-renewed" is not a synonym for "deemed toxic". EU PPDB records that
    a non-renewal happened and when, not why; commercial or administrative
    reasons are real and this data cannot distinguish them from a safety
    finding.
    """
    approvals: dict[str, date] = {}
    for e in regevents:
        if e.kind != RegulatoryEventKind.APPROVAL:
            continue
        if e.substance_id not in approvals or e.event_date < approvals[e.substance_id]:
            approvals[e.substance_id] = e.event_date
    non_renewed = {e.substance_id for e in regevents if e.kind == RegulatoryEventKind.NON_RENEWAL}

    counts = {label: {"total": 0, "non_renewed": 0} for label, _lo, _hi in bands}
    for substance_id, approved in approvals.items():
        years = (today - approved).days / 365.25
        for label, lo, hi in bands:
            if lo <= years < hi:
                counts[label]["total"] += 1
                if substance_id in non_renewed:
                    counts[label]["non_renewed"] += 1
                break

    rows = []
    for label, _lo, _hi in bands:
        c = counts[label]
        rate = c["non_renewed"] / c["total"] if c["total"] else None
        rows.append(
            {
                "age_band": label,
                "total": c["total"],
                "non_renewed": c["non_renewed"],
                "still_active": c["total"] - c["non_renewed"],
                "non_renewal_rate": rate,
            }
        )
    return rows
