"""Tests for the anchor-cohort measurement.

These fix the arithmetic and the chance baseline, not any particular result for
the TFA cohort: that number is allowed to move when the model or the data move,
and `pipeline/32` is what reports it.
"""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from hazium.benchmark.anchor import cohort_ranks

RANKED = [f"substance:cas:{i}" for i in range(1, 101)]


def _sid(n: int) -> str:
    return f"substance:cas:{n}"


def test_ranks_are_one_based_and_positional():
    result = cohort_ranks(RANKED, [_sid(1), _sid(50), _sid(100)], top_k=10)
    assert result.ranks == {_sid(1): 1, _sid(50): 50, _sid(100): 100}
    assert result.population == 100


def test_expected_hits_follow_the_population_share():
    result = cohort_ranks(RANKED, [_sid(i) for i in (1, 2, 3, 4)], top_k=25)
    # Four members, a quarter of the ranking in the band: one by chance.
    assert result.expected_in_top_k == pytest.approx(1.0)
    assert result.hits_in_top_k == 4
    assert result.beats_chance


def test_a_cohort_at_the_bottom_does_not_beat_chance():
    result = cohort_ranks(RANKED, [_sid(i) for i in (95, 96, 97, 98)], top_k=25)
    assert result.hits_in_top_k == 0
    assert result.median_percentile > 0.5
    assert not result.beats_chance


def test_one_lucky_member_is_not_a_detection():
    """The failure mode this module exists to catch.

    A single cohort member high in the band reads as a hit if it is the only
    one anyone looks at. The cohort median is what settles it.
    """
    result = cohort_ranks(RANKED, [_sid(i) for i in (2, 80, 85, 90, 95, 99)], top_k=20)
    assert result.hits_in_top_k == 1
    assert result.expected_in_top_k == pytest.approx(1.2)
    assert result.median_percentile > 0.5
    assert not result.beats_chance


def test_missing_members_are_reported_not_imputed():
    result = cohort_ranks(RANKED, [_sid(1), _sid(3), "substance:cas:absent"], top_k=10)
    assert result.missing == ("substance:cas:absent",)
    assert result.median_rank == 2.0
    assert result.expected_in_top_k == pytest.approx(0.2)


def test_duplicate_cohort_entries_are_counted_once():
    result = cohort_ranks(RANKED, [_sid(1), _sid(1), _sid(3)], top_k=10)
    assert result.ranks == {_sid(1): 1, _sid(3): 3}
    assert result.expected_in_top_k == pytest.approx(0.2)


def test_duplicate_ranking_entries_are_rejected():
    with pytest.raises(ValueError, match="duplicates"):
        cohort_ranks([_sid(1), _sid(1)], [_sid(1)])


def test_empty_cohort_yields_no_median():
    result = cohort_ranks(RANKED, [], top_k=10)
    assert result.ranks == {}
    assert math.isnan(result.median_rank)
    assert not result.beats_chance


def test_band_cannot_exceed_the_population():
    result = cohort_ranks(RANKED[:5], [_sid(1)], top_k=100)
    assert result.top_k == 5
    assert result.expected_in_top_k == pytest.approx(1.0)


def test_result_is_frozen():
    result = cohort_ranks(RANKED, [_sid(1)], top_k=10)
    with pytest.raises(ValidationError):
        result.population = 1
