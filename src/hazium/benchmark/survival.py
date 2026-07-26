"""Discrete-time survival framing: does the evidence predict *who* fails?

HEWB asks whether a substance was ever withdrawn, over a population where most
substances were never approved and so could never be withdrawn at all. That
question is answered largely by identifying the eligible minority, and approval
age does that on its own: ranking on age alone reaches 98% of the full model's
average precision and reproduces its headline lead times exactly.

The failure is in the question, not the data. A withdrawal can only happen when
an approval comes up for renewal, so any target of the form "was it ever
withdrawn" mixes *whether* with *when*, and time wins.

This module asks the separable question instead. The unit is one approved
substance in one year at risk, and the outcome is whether the withdrawal landed
inside a horizon starting that year. Time then enters as the baseline hazard,
which is what it is, and the evidence is left to explain the rest.

Measured on that panel, with folds grouped by substance so no substance straddles
a split, the evidence adds a real and independently-verified amount:

* age alone reaches AP 0.102, the evidence alone 0.180, and the two together
  0.242, against a seed spread of +/-0.014,
* the signal survives lagging every feature by three years, decaying from +0.124
  to +0.026 rather than collapsing, so it is not an artefact of activity
  immediately before a decision,
* a block permutation test over whole substance histories puts it at p = 0.024,
* and in a genuine forward split (fit on 2019 and earlier, score 2020 onward)
  the top 50 contains 11 real withdrawals against approval age's 4.

Approval age is about 47% recoverable from the evidence features (R^2 = 0.473,
grouped by substance), so "evidence only" is not an age-free arm. This once read
as R^2 = -0.009 and "genuinely separate", measured with an unshuffled KFold that
split this year-ordered panel on time; see `pipeline/32` for both figures. The
comparison above is unaffected, since both arms carry the age features.

The honest limits are equally measurable. A linear model recovers only a fifth of what
gradient boosting does, so the effect lives in interactions. And 75 of the 102
events fall in the 2017-2021 renewal wave, which is the binding limit: forward
splits fit on 2014 or 2015 give a *negative* delta, and subsampling shows this is
not a sample-size floor. Holding the test set fixed and varying only how many
training events are kept, the delta stays positive down to four events. What
fails is transfer between regulatory eras, not learning from few examples.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict

from hazium.graph.store import TemporalGraph
from hazium.ml.dataset import build_dataset
from hazium.models import (
    CLHIntentionRecord,
    LiteratureVolumeRecord,
    RegulatoryEvent,
    RegulatoryEventKind,
    SalesRecord,
)

#: Column holding the substance id, used to group cross-validation folds.
SUBJECT = "_substance"

#: Column holding the year a row is at risk in.
YEAR = "_year"

#: Column holding the outcome for that row.
EVENT = "_event"

#: The two features that encode time rather than evidence. Reported as their own
#: arm everywhere, because the whole point is to keep them separable.
AGE_FEATURES: tuple[str, ...] = ("eu_has_approval", "eu_years_since_first_approval")

#: Evidence feature groups, kept named so each can be added to age on its own.
#: EFSA activity and ECHA CLH intentions read the regulator's own pipeline; the
#: rest do not. Measured as blocks they contribute +0.085 and +0.067, so the
#: result does not rest on reading regulatory intent.
EVIDENCE_GROUPS: dict[str, tuple[str, ...]] = {
    "clp": (
        "clp_n_hazard_codes",
        "clp_n_distinct_atp",
        "clp_has_cmr",
        "clp_has_aquatic_chronic_1",
        "clp_has_stot",
        "clp_years_since_last_classification",
    ),
    "efsa": ("efsa_n_assessments", "efsa_years_since_last", "efsa_assessment_span_years"),
    "sales": (
        "sales_latest_tonnage",
        "sales_mean_tonnage",
        "sales_trend_slope",
        "sales_volatility",
        "sales_years_on_market",
        "sales_max_yoy_jump",
    ),
    "graph": (
        "graph_degree",
        "graph_shared_hazard_substance_count",
        "graph_metabolite_degree",
    ),
    "literature": ("lit_hazard_percentile", "lit_has_literature_signal"),
    "clh": ("clh_has_intention", "clh_years_since_intention"),
}

#: Groups that read the regulator's own process rather than independent evidence.
IN_FUNNEL_GROUPS: frozenset[str] = frozenset({"efsa", "clh"})

EVIDENCE_FEATURES: tuple[str, ...] = tuple(
    column for group in EVIDENCE_GROUPS.values() for column in group
)


class PanelSpec(BaseModel):
    """How a survival panel is constructed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    first_year: int = 2009
    last_year: int = 2024
    horizon_years: int = 1
    positive_kind: RegulatoryEventKind = RegulatoryEventKind.NON_RENEWAL


def first_event_dates(events: list[RegulatoryEvent], kind: RegulatoryEventKind) -> dict[str, date]:
    """Earliest event of ``kind`` per substance.

    The earliest is taken rather than the latest because a substance can carry
    several records for one withdrawal, and the benchmark anchors lead time to
    the first regulatory action.
    """
    out: dict[str, date] = {}
    for event in events:
        if event.kind is not kind:
            continue
        seen = out.get(event.substance_id)
        if seen is None or event.event_date < seen:
            out[event.substance_id] = event.event_date
    return out


def build_panel(
    graph: TemporalGraph,
    sales: list[SalesRecord],
    events: list[RegulatoryEvent],
    lit_records: list[LiteratureVolumeRecord] = (),
    spec: PanelSpec | None = None,
    clh_records: list[CLHIntentionRecord] = (),
) -> pd.DataFrame:
    """One row per approved substance per year at risk.

    A row exists when the substance holds EU approval at the start of the year
    and has not already been withdrawn. Features are read at that year's cutoff,
    so every value predates the outcome window by construction and the temporal
    discipline of `build_dataset` carries through unchanged.

    Args:
        graph: The temporal knowledge graph.
        sales: Sales records, already resolved to substance ids.
        events: Regulatory events, used both for features and for the outcome.
        lit_records: Optional literature-volume records.
        spec: Panel configuration; defaults are the reported ones.
        clh_records: Optional ECHA CLH-intention records. Passing none leaves
            that whole feature group at zero, which silently turns the
            in-funnel contribution into EFSA alone; the callers pass the
            snapshot for that reason.

    Returns:
        A frame of feature columns plus ``_substance``, ``_year`` and ``_event``.
    """
    spec = spec or PanelSpec()
    withdrawal = first_event_dates(events, spec.positive_kind)
    frames: list[pd.DataFrame] = []

    for year in range(spec.first_year, spec.last_year + 1):
        cutoff = date(year, 1, 1)
        features, _label, ids = build_dataset(
            graph, sales, events, cutoff, lit_records=lit_records, clh_records=clh_records
        )
        approved = features["eu_has_approval"].to_numpy() > 0
        rows = features[approved].copy()
        subject_ids = [sid for sid, keep in zip(ids, approved) if keep]

        at_risk: list[bool] = []
        outcome: list[int] = []
        for sid in subject_ids:
            when = withdrawal.get(sid)
            if when is not None and when < cutoff:
                # Already withdrawn: out of the risk set, not a permanent negative.
                at_risk.append(False)
                outcome.append(0)
                continue
            at_risk.append(True)
            outcome.append(
                1 if when is not None and year <= when.year < year + spec.horizon_years else 0
            )

        rows = rows[at_risk]
        rows[EVENT] = [o for o, keep in zip(outcome, at_risk) if keep]
        rows[SUBJECT] = [s for s, keep in zip(subject_ids, at_risk) if keep]
        rows[YEAR] = year
        frames.append(rows)

    if not frames:
        return pd.DataFrame(columns=[*AGE_FEATURES, EVENT, SUBJECT, YEAR])
    return pd.concat(frames, ignore_index=True)


def baseline_hazard(
    panel: pd.DataFrame, edges: tuple[int, ...] = (0, 5, 10, 15, 20, 99)
) -> pd.DataFrame:
    """Withdrawal rate by approval age, with no model involved.

    This is the shape any learned model is competing against, and it is steep:
    roughly 0.3% a year under five years of approval against 22% past twenty.
    """
    ages = panel["eu_years_since_first_approval"].to_numpy()
    y = panel[EVENT].to_numpy()
    rows = []
    for low, high in zip(edges, edges[1:]):
        mask = (ages >= low) & (ages < high)
        if mask.sum():
            rows.append(
                {
                    "age_from": low,
                    "age_to": high,
                    "rows": int(mask.sum()),
                    "events": int(y[mask].sum()),
                    "hazard": float(y[mask].mean()),
                }
            )
    return pd.DataFrame(rows)


def feature_columns(
    *, age: bool = True, evidence: bool = True, groups: tuple[str, ...] = ()
) -> list[str]:
    """Assemble a feature list for one arm of the comparison.

    Args:
        age: Include the two approval-age features.
        evidence: Include every evidence group. Ignored when ``groups`` is given.
        groups: Restrict evidence to these named groups.

    Returns:
        Column names, in a stable order.
    """
    cols: list[str] = list(AGE_FEATURES) if age else []
    if groups:
        for name in groups:
            cols.extend(EVIDENCE_GROUPS[name])
    elif evidence:
        cols.extend(EVIDENCE_FEATURES)
    return cols


def forward_split(panel: pd.DataFrame, train_through: int) -> tuple[np.ndarray, np.ndarray]:
    """Boolean masks for a genuine forward evaluation.

    Grouped cross-validation lets a fold train on 2023 and test on 2011, which
    deployment never gets to do. This splits strictly on time instead.

    Args:
        panel: The survival panel.
        train_through: Last year included in training.

    Returns:
        ``(train_mask, test_mask)``.
    """
    train = (panel[YEAR] <= train_through).to_numpy()
    return train, ~train
