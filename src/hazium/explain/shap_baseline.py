"""SHAP explanations over the fitted XGBoost baseline.

Explainability hierarchy position #2 (``MANIFESTO.md`` §7): evidence paths in
the graph are primary; this is the tabular-SHAP layer beneath them. The model
explained here is fit in-sample (unlike the out-of-fold ranking evaluation in
``ml/baseline.py``) because the question SHAP answers is different: not "how
well does this rank held-out substances" but "what did the model learn to
associate with risk", which is a property of the fitted model itself.
"""

from __future__ import annotations

import pandas as pd
import shap

from hazium.ml.baseline import make_model


def fit_and_explain(
    X: pd.DataFrame, y: pd.Series, seed: int = 42
) -> tuple[object, shap.Explanation]:
    """Fit the baseline model on the full data and compute its SHAP values."""
    model = make_model(y, seed)
    model.fit(X, y)
    explainer = shap.TreeExplainer(model)
    shap_values = explainer(X)
    return model, shap_values


def global_importance(shap_values: shap.Explanation) -> list[tuple[str, float]]:
    """Feature names ranked by mean absolute SHAP value, descending."""
    mean_abs = pd.DataFrame(shap_values.values, columns=shap_values.feature_names).abs().mean()
    return list(mean_abs.sort_values(ascending=False).items())


#: Feature groups by position relative to the EU non-renewal regulatory funnel
#: (``SOURCE_ENHANCEMENT_SCOPE.md``). This split answers the one question the
#: aggregate AP hides: does the early-warning claim rest on *independent*
#: outside-funnel signal, or is the model just reading the regulator's own
#: pipeline (which would score well on HEWB and prove little)?
#:
#: * ``approval_age`` — EU approval existence and years-since-first-approval.
#:   Held out as its own group on purpose, not folded into ``inside_funnel``:
#:   it is a temporal *prior* (older approvals face more renewal cycles), not a
#:   concern signal, and it dominates the model (~half of total mean|SHAP|). The
#:   DEV_LOG (``pipeline/13``) already documents this dominance and mitigates it
#:   with cohort-relative ranking. Burying it inside ``inside_funnel`` would both
#:   overstate reliance on genuine regulatory-concern signals and mask that,
#:   among the *evidence* features, literature stands on par with EFSA/CLH.
#: * ``inside_funnel`` — signals from the regulatory concern process itself:
#:   EFSA peer-review activity, ECHA CLH intentions. High precision, but a model
#:   leaning only here "saw the paperwork move", not the hazard early.
#: * ``outside_funnel`` — independent scientific-literature volume (Europe PMC).
#:   Longest lead, name-joined, noisy: this is where "saw it before regulators
#:   acted" actually lives. The differentiation.
#: * ``intrinsic`` — the substance's own hazard / exposure / graph profile (CLP
#:   harmonised hazard, KEMI sales, graph structure). Funnel-neutral: neither the
#:   regulator's homework nor independent early-warning literature, but real
#:   predictive properties. Reported apart rather than force-fit to either side.
FUNNEL_GROUPS: dict[str, tuple[str, ...]] = {
    "approval_age": (
        "eu_has_approval",
        "eu_years_since_first_approval",
    ),
    "inside_funnel": (
        "efsa_n_assessments",
        "efsa_years_since_last",
        "efsa_assessment_span_years",
        "clh_has_intention",
        "clh_years_since_intention",
    ),
    "outside_funnel": (
        "lit_hazard_percentile",
        "lit_has_literature_signal",
    ),
    "intrinsic": (
        "clp_n_hazard_codes",
        "clp_n_distinct_atp",
        "clp_has_cmr",
        "clp_has_aquatic_chronic_1",
        "clp_has_stot",
        "clp_years_since_last_classification",
        "sales_latest_tonnage",
        "sales_mean_tonnage",
        "sales_trend_slope",
        "sales_volatility",
        "sales_years_on_market",
        "sales_max_yoy_jump",
        "graph_degree",
        "graph_shared_hazard_substance_count",
        "graph_metabolite_degree",
    ),
}


def grouped_importance(
    shap_values: shap.Explanation,
    groups: dict[str, tuple[str, ...]] = FUNNEL_GROUPS,
) -> list[dict]:
    """Mean-abs SHAP summed within each feature group, with each group's share.

    Fails loudly if ``groups`` does not partition the model's features exactly
    (every feature in exactly one group, no unknown names): a silently
    unclassified feature would make the funnel shares misleading, and a feature
    added later must be deliberately assigned, not dropped. Returns one dict per
    group ``{group, mean_abs_shap, share}``, ``share`` summing to 1.
    """
    per_feature = dict(global_importance(shap_values))
    feature_names = set(per_feature)
    grouped_names = [c for cols in groups.values() for c in cols]
    grouped_set = set(grouped_names)
    if len(grouped_names) != len(grouped_set):
        raise ValueError("FUNNEL_GROUPS assigns a feature to more than one group")
    missing = feature_names - grouped_set
    unknown = grouped_set - feature_names
    if missing or unknown:
        raise ValueError(
            f"funnel groups do not partition the features exactly: "
            f"unassigned={sorted(missing)} unknown={sorted(unknown)}"
        )

    total = sum(per_feature.values()) or 1.0
    rows = []
    for group, cols in groups.items():
        s = sum(per_feature.get(c, 0.0) for c in cols)
        rows.append({"group": group, "mean_abs_shap": s, "share": s / total})
    return rows


def explain_row(
    shap_values: shap.Explanation, ids: list[str], substance_id: str
) -> list[tuple[str, float]]:
    """Per-feature SHAP contributions for one substance, most-positive first.

    Raises ``ValueError`` if ``substance_id`` isn't in ``ids`` (the same
    population the SHAP values were computed over) — a silent empty result
    would be easy to mistake for "no contribution" instead of "wrong id".
    """
    if substance_id not in ids:
        raise ValueError(f"substance not in this cutoff's population: {substance_id!r}")
    i = ids.index(substance_id)
    row = pd.Series(shap_values.values[i], index=shap_values.feature_names)
    return list(row.sort_values(ascending=False).items())
