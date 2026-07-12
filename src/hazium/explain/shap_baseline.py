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
