"""Ranking metrics on toy rankings with known answers."""

import numpy as np

from hazium.ml.evaluate import (
    average_precision,
    bootstrap_ci,
    lift_at_k,
    precision_at_k,
    recall_at_k,
)

# perfect ranking: both positives are the top two scores
_Y_PERFECT = np.array([1, 0, 1, 0, 0])
_SCORES_PERFECT = np.array([0.9, 0.1, 0.8, 0.05, 0.02])

# inverted ranking: positives are the two lowest scores
_Y_INVERTED = np.array([1, 0, 1, 0, 0])
_SCORES_INVERTED = np.array([0.02, 0.9, 0.05, 0.8, 0.1])


class TestAveragePrecision:
    def test_perfect_ranking_is_one(self) -> None:
        assert average_precision(_Y_PERFECT, _SCORES_PERFECT) == 1.0

    def test_no_positives_is_zero_not_undefined(self) -> None:
        y = np.zeros(5)
        assert average_precision(y, _SCORES_PERFECT) == 0.0

    def test_inverted_ranking_scores_worse_than_perfect(self) -> None:
        assert average_precision(_Y_INVERTED, _SCORES_INVERTED) < average_precision(
            _Y_PERFECT, _SCORES_PERFECT
        )


class TestPrecisionAtK:
    def test_perfect_ranking_top_2_all_positive(self) -> None:
        assert precision_at_k(_Y_PERFECT, _SCORES_PERFECT, k=2) == 1.0

    def test_k_larger_than_population_clips(self) -> None:
        # 2 positives out of 5 total -> precision@10 == precision@5 == 2/5
        assert precision_at_k(_Y_PERFECT, _SCORES_PERFECT, k=10) == 2 / 5

    def test_zero_k_is_zero(self) -> None:
        assert precision_at_k(_Y_PERFECT, _SCORES_PERFECT, k=0) == 0.0

    def test_inverted_ranking_top_2_none_positive(self) -> None:
        assert precision_at_k(_Y_INVERTED, _SCORES_INVERTED, k=2) == 0.0


class TestRecallAtK:
    def test_perfect_ranking_top_2_full_recall(self) -> None:
        assert recall_at_k(_Y_PERFECT, _SCORES_PERFECT, k=2) == 1.0

    def test_no_positives_is_zero(self) -> None:
        y = np.zeros(5)
        assert recall_at_k(y, _SCORES_PERFECT, k=2) == 0.0

    def test_inverted_ranking_top_2_zero_recall(self) -> None:
        assert recall_at_k(_Y_INVERTED, _SCORES_INVERTED, k=2) == 0.0


class TestLiftAtK:
    def test_perfect_ranking_lift_above_one(self) -> None:
        # base rate 2/5 = 0.4; precision@2 = 1.0 -> lift = 2.5
        assert lift_at_k(_Y_PERFECT, _SCORES_PERFECT, k=2) == 2.5

    def test_no_positives_is_zero(self) -> None:
        y = np.zeros(5)
        assert lift_at_k(y, _SCORES_PERFECT, k=2) == 0.0


class TestBootstrapCi:
    def test_returns_ordered_interval(self) -> None:
        lo, hi = bootstrap_ci(_Y_PERFECT, _SCORES_PERFECT, average_precision, n_boot=50)
        assert lo <= hi

    def test_empty_input_returns_zero_zero(self) -> None:
        assert bootstrap_ci(np.array([]), np.array([]), average_precision, n_boot=10) == (0.0, 0.0)

    def test_handles_resamples_with_zero_positives_without_raising(self) -> None:
        # a resample of an already-imbalanced array can easily draw zero positives;
        # average_precision must not raise for that resample
        y = np.array([1, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        scores = np.random.default_rng(0).random(10)
        lo, hi = bootstrap_ci(y, scores, average_precision, n_boot=100)
        assert 0.0 <= lo <= hi <= 1.0
