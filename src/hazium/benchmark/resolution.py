"""Track what actually happens to watchlist substances, including the misses.

A forward watchlist is only worth publishing if it can be marked. The hard part
is not recording the hits, it is confirming the *false alarms*, because absence
of a ban is not evidence of a correct approval: it is indistinguishable from a
decision that has not been taken yet. Precision at recent HEWB cutoffs is
depressed for exactly this reason, correlating with how many years of future
each cutoff has had at r = 0.957.

The way out is that every EU approval carries a dated expiry, and at that date
the Commission must act. That converts an open-ended wait into a schedule:
54% of the current top 50 reach their expiry by the end of 2027.

Three outcomes are therefore distinguishable rather than two:

* the approval lapses, which confirms the ranking,
* it is renewed for a full term, which **confirms a false positive**,
* it is extended by a short procedural step, which resolves nothing and is by
  far the most common way an EU renewal deadline passes.

Missing the third would be the trap. A technical extension looks like survival
and would silently be scored as a false positive if only status were read, so
the length of the new term is what separates them.

Observations are stored raw and classified on read. The renewal/extension
boundary below is a heuristic about EU practice, not a fact from the register,
so keeping the dates means a wrong threshold can be corrected later without
having lost anything.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

#: A renewal under Reg. (EC) No 1107/2009 grants a long term (up to 15 years),
#: while a technical extension buys months while an assessment finishes. Three
#: years sits in the empty space between the two. It is a judgement about
#: practice, not a rule from the regulation, which is why the raw dates are kept.
RENEWAL_MIN_EXTENSION_YEARS = 3.0

#: Status strings as printed in the EU Pesticides Database export.
STATUS_APPROVED = "Approved"
STATUS_NOT_APPROVED = "Not approved"
STATUS_PENDING = "Pending"


class Resolution(StrEnum):
    """What has become of a watchlist entry."""

    PENDING = "pending"
    OVERDUE = "overdue"
    NOT_RENEWED = "not_renewed"
    RENEWED = "renewed"
    EXTENDED = "extended"
    SHORTENED = "shortened"
    UNKNOWN = "unknown"


#: Outcomes that settle the question. Everything else is still open, and must
#: never be counted as a false positive.
RESOLVED: frozenset[Resolution] = frozenset({Resolution.NOT_RENEWED, Resolution.RENEWED})


class ApprovalState(BaseModel):
    """A substance's approval status and expiry as read on one date."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    substance_id: str
    name: str
    status: str
    expiry: date | None = None
    observed_at: date = Field(description="When the register was read")


class TrackedEntry(BaseModel):
    """One watchlist substance, its baseline reading, and its latest reading."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    substance_id: str
    name: str
    rank: int
    baseline: ApprovalState
    latest: ApprovalState


def _years_between(earlier: date, later: date) -> float:
    return (later - earlier).days / 365.25


def classify(entry: TrackedEntry, today: date) -> Resolution:
    """Decide what has happened to one tracked substance.

    Args:
        entry: The substance with its baseline and latest register readings.
        today: The date to judge "still in the future" against.

    Returns:
        The outcome. Only ``NOT_RENEWED`` and ``RENEWED`` settle anything; the
        rest mean the decision has not been taken.
    """
    base, now = entry.baseline, entry.latest

    # A substance already out of approval when tracking began was never a live
    # prediction, so it cannot be scored. pipeline/13 censors these, but a
    # hand-assembled watchlist might not.
    if base.status == STATUS_NOT_APPROVED:
        return Resolution.UNKNOWN

    if now.status == STATUS_NOT_APPROVED:
        return Resolution.NOT_RENEWED

    if now.status == STATUS_PENDING:
        return Resolution.PENDING

    if now.status != STATUS_APPROVED:
        return Resolution.UNKNOWN

    # Still approved. The question is whether the term was genuinely renewed,
    # merely nudged forward, or has simply not been dealt with.
    if base.expiry is None or now.expiry is None:
        return Resolution.UNKNOWN

    if now.expiry > base.expiry:
        gained = _years_between(base.expiry, now.expiry)
        if gained >= RENEWAL_MIN_EXTENSION_YEARS:
            return Resolution.RENEWED
        return Resolution.EXTENDED

    if now.expiry < base.expiry:
        return Resolution.SHORTENED

    return Resolution.PENDING if now.expiry > today else Resolution.OVERDUE


def summarise(entries: list[TrackedEntry], today: date) -> dict[Resolution, int]:
    """Count outcomes across a tracked watchlist."""
    counts: dict[Resolution, int] = {r: 0 for r in Resolution}
    for entry in entries:
        counts[classify(entry, today)] += 1
    return counts


def confirmed_precision(entries: list[TrackedEntry], today: date) -> tuple[int, int, float | None]:
    """Precision over settled entries only.

    Counting unresolved entries as failures is what depresses recent-cutoff
    precision, so they are excluded rather than assumed wrong.

    Args:
        entries: Tracked watchlist entries.
        today: Date to judge pending status against.

    Returns:
        ``(hits, settled, precision)``. Precision is None while nothing has
        settled, because 0/0 is not zero.
    """
    hits = settled = 0
    for entry in entries:
        outcome = classify(entry, today)
        if outcome in RESOLVED:
            settled += 1
            if outcome is Resolution.NOT_RENEWED:
                hits += 1
    return hits, settled, (hits / settled if settled else None)
