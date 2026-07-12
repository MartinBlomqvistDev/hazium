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
    "eu_has_approval",
    "eu_years_since_first_approval",
]


def build_dataset(
    graph: TemporalGraph,
    sales: list[SalesRecord],
    regevents: list[RegulatoryEvent],
    cutoff: date,
) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    """Build (X, y, substance_ids) for one rolling-origin cutoff.

    Population: substances present in ``graph.as_of(cutoff)`` (≥1 dated
    pre-cutoff fact), **excluding** any substance that already has a
    ``NON_RENEWAL`` event dated before the cutoff. A substance that lost EU
    approval before T is not a member of the "at risk of future non-renewal"
    population going forward — including it would either double-count an
    already-realized event or degenerate into a permanent, uninformative
    negative. This censoring rule is not explicit in ``V1_SCOPE.md``'s task
    section but follows directly from what "future regulatory action" means;
    documented here since it is not obvious from the label definition alone.

    Label: 1 iff the substance has a ``NON_RENEWAL`` event dated `>= cutoff`.
    """
    view = graph.as_of(cutoff)
    already_non_renewed = {
        e.substance_id
        for e in regevents
        if e.kind == RegulatoryEventKind.NON_RENEWAL and e.event_date < cutoff
    }
    population = [
        n.id
        for n in view.nodes()
        if n.type == NodeType.SUBSTANCE and n.id not in already_non_renewed
    ]

    future_non_renewals = {
        e.substance_id
        for e in regevents
        if e.kind == RegulatoryEventKind.NON_RENEWAL and e.event_date >= cutoff
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
        [1 if sid in future_non_renewals else 0 for sid in population],
        index=population,
        name="label",
    )
    return X, y, population
