"""SHAP explanation wiring on a small synthetic dataset."""

import numpy as np
import pandas as pd
import pytest

from hazium.explain.shap_baseline import explain_row, fit_and_explain, global_importance
from hazium.ml.dataset import FEATURE_COLUMNS


def _toy_dataset(n: int = 30, n_pos: int = 8) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    rng = np.random.default_rng(0)
    ids = [f"substance:cas:{i:05d}-00-0" for i in range(n)]
    X = pd.DataFrame(rng.random((n, len(FEATURE_COLUMNS))), columns=FEATURE_COLUMNS, index=ids)
    y = pd.Series([1] * n_pos + [0] * (n - n_pos), index=ids, name="label")
    return X, y, ids


class TestFitAndExplain:
    def test_shap_values_shape_matches_input(self) -> None:
        X, y, _ = _toy_dataset()
        _, shap_values = fit_and_explain(X, y)
        assert shap_values.values.shape == (len(X), len(FEATURE_COLUMNS))


class TestGlobalImportance:
    def test_returns_all_features_sorted_descending(self) -> None:
        X, y, _ = _toy_dataset()
        _, shap_values = fit_and_explain(X, y)
        importance = global_importance(shap_values)
        names = [name for name, _ in importance]
        values = [value for _, value in importance]
        assert set(names) == set(FEATURE_COLUMNS)
        assert values == sorted(values, reverse=True)


class TestExplainRow:
    def test_returns_one_value_per_feature(self) -> None:
        X, y, ids = _toy_dataset()
        _, shap_values = fit_and_explain(X, y)
        row = explain_row(shap_values, ids, ids[0])
        assert len(row) == len(FEATURE_COLUMNS)

    def test_unknown_substance_id_raises(self) -> None:
        X, y, ids = _toy_dataset()
        _, shap_values = fit_and_explain(X, y)
        with pytest.raises(ValueError, match="not in this cutoff's population"):
            explain_row(shap_values, ids, "substance:cas:99999-99-9")
