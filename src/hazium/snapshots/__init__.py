"""Dated snapshot capture for sources that publish current state only.

Several Hazium signals are unusable today not because the data is weak but
because it is *undated*: a register publishes what is true now and keeps no
history, so a fact observed in 2026 cannot be placed at a 2015 cutoff without
leaking. This package is the fix, and it only works forwards: capture the
sources on a schedule from today, stamp every capture with the date it was
made, and the archive becomes legitimate pre-cutoff evidence for future
cutoffs.

The contract, and the reason this package exists at all:

    ``captured_at`` is the date Hazium observed the payload, and it is the
    ``known_at`` of anything derived from that payload.

That is deliberately conservative. The underlying fact may have become true
earlier; we only assert that it was observable when we observed it. Claiming an
earlier date would be exactly the leakage the project forbids.

See ``registry.py`` for the sources captured and the named future use each one
serves. Sources are added only with such a use, because an unused archive is
maintenance cost with no payoff.
"""

from __future__ import annotations

from hazium.snapshots.models import Observation, RunReport, SourceSpec
from hazium.snapshots.registry import REGISTRY, spec_by_name
from hazium.snapshots.runner import exit_code, run_sources
from hazium.snapshots.store import SnapshotStore

__all__ = [
    "REGISTRY",
    "Observation",
    "RunReport",
    "SnapshotStore",
    "SourceSpec",
    "exit_code",
    "run_sources",
    "spec_by_name",
]
