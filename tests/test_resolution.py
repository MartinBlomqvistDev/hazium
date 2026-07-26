"""Tests for watchlist resolution tracking.

The cases that matter are the ones that separate a settled outcome from an
open one. Scoring an unresolved entry as a false positive is the failure this
module exists to prevent.
"""

from datetime import date

import pytest

from hazium.benchmark.resolution import (
    RESOLVED,
    ApprovalState,
    Resolution,
    TrackedEntry,
    classify,
    confirmed_precision,
    summarise,
)

TODAY = date(2027, 6, 1)


def _entry(
    *,
    base_status: str = "Approved",
    base_expiry: date | None = date(2026, 12, 1),
    now_status: str = "Approved",
    now_expiry: date | None = date(2026, 12, 1),
    rank: int = 1,
) -> TrackedEntry:
    return TrackedEntry(
        substance_id="substance:cas:1-2-3",
        name="Testonium",
        rank=rank,
        baseline=ApprovalState(
            substance_id="substance:cas:1-2-3",
            name="Testonium",
            status=base_status,
            expiry=base_expiry,
            observed_at=date(2026, 7, 25),
        ),
        latest=ApprovalState(
            substance_id="substance:cas:1-2-3",
            name="Testonium",
            status=now_status,
            expiry=now_expiry,
            observed_at=TODAY,
        ),
    )


def test_lapsed_approval_is_a_hit() -> None:
    assert classify(_entry(now_status="Not approved"), TODAY) is Resolution.NOT_RENEWED


def test_full_term_renewal_confirms_a_false_positive() -> None:
    """A long new term is a decision: the Commission looked and said yes."""
    entry = _entry(now_expiry=date(2041, 12, 1))
    assert classify(entry, TODAY) is Resolution.RENEWED


def test_short_technical_extension_does_not_confirm_anything() -> None:
    """The trap this module exists for.

    A procedural extension looks like survival. Scored on status alone it would
    read as a false positive, when in fact no decision has been taken.
    """
    entry = _entry(now_expiry=date(2027, 12, 1))
    assert classify(entry, TODAY) is Resolution.EXTENDED
    assert classify(entry, TODAY) not in RESOLVED


def test_unchanged_future_expiry_is_pending() -> None:
    entry = _entry(base_expiry=date(2030, 1, 1), now_expiry=date(2030, 1, 1))
    assert classify(entry, TODAY) is Resolution.PENDING


def test_unchanged_past_expiry_is_overdue_not_a_verdict() -> None:
    """EU renewal deadlines routinely pass with nothing recorded."""
    entry = _entry(base_expiry=date(2026, 12, 1), now_expiry=date(2026, 12, 1))
    assert classify(entry, TODAY) is Resolution.OVERDUE
    assert classify(entry, TODAY) not in RESOLVED


def test_shortened_term_is_flagged_rather_than_silently_bucketed() -> None:
    entry = _entry(now_expiry=date(2026, 8, 1))
    assert classify(entry, TODAY) is Resolution.SHORTENED


def test_substance_already_unapproved_at_baseline_cannot_be_scored() -> None:
    entry = _entry(base_status="Not approved", now_status="Not approved")
    assert classify(entry, TODAY) is Resolution.UNKNOWN


def test_pending_status_is_pending() -> None:
    assert classify(_entry(now_status="Pending"), TODAY) is Resolution.PENDING


def test_missing_expiry_is_unknown_rather_than_assumed() -> None:
    assert classify(_entry(now_expiry=None), TODAY) is Resolution.UNKNOWN
    assert classify(_entry(base_expiry=None), TODAY) is Resolution.UNKNOWN


def test_precision_counts_only_settled_entries() -> None:
    entries = [
        _entry(now_status="Not approved", rank=1),
        _entry(now_expiry=date(2041, 12, 1), rank=2),
        _entry(now_expiry=date(2027, 12, 1), rank=3),
        _entry(base_expiry=date(2030, 1, 1), now_expiry=date(2030, 1, 1), rank=4),
    ]
    hits, settled, precision = confirmed_precision(entries, TODAY)
    assert (hits, settled) == (1, 2)
    assert precision == pytest.approx(0.5)


def test_precision_is_none_before_anything_settles() -> None:
    """0/0 is not zero, and reporting it as zero would libel the model."""
    entries = [_entry(base_expiry=date(2030, 1, 1), now_expiry=date(2030, 1, 1))]
    hits, settled, precision = confirmed_precision(entries, TODAY)
    assert (hits, settled, precision) == (0, 0, None)


def test_summarise_counts_every_outcome_bucket() -> None:
    entries = [
        _entry(now_status="Not approved", rank=1),
        _entry(now_expiry=date(2041, 12, 1), rank=2),
    ]
    counts = summarise(entries, TODAY)
    assert counts[Resolution.NOT_RENEWED] == 1
    assert counts[Resolution.RENEWED] == 1
    assert sum(counts.values()) == len(entries)
