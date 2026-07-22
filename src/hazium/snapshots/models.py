"""Data contracts for snapshot capture.

Mirrors ``hazium.models``: frozen Pydantic, provenance and temporal validity on
every record, corrections are new records rather than mutations. The manifest is
append-only for the same reason the graph is: an observation that happened
cannot later un-happen.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Cadence(StrEnum):
    """How often a source is worth re-capturing.

    Advisory metadata, not a scheduler: the workflow decides what actually runs.
    It records intent so a reader can tell whether a gap in the manifest is
    expected or a fault.
    """

    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ANNUAL = "annual"


class CollectorKind(StrEnum):
    """How a source is fetched.

    Each value maps to one function in ``collectors.py``. Adding a source with
    an existing kind is configuration; adding a new kind is code.
    """

    FILE = "file"
    """A single URL returning the whole payload (PDF, XLSX, JSON document)."""

    OGC_FEATURES_WINDOW = "ogc_features_window"
    """An OGC API - Features collection, paged over a rolling date window.

    Deliberately a rolling window rather than a strict high-water mark: these
    registers publish results well after the sampling date, so a narrow window
    anchored on the previous run would silently miss late-registered records.
    """

    PPDB_DETAILS = "ppdb_details"
    """The EU Pesticides Database per-substance details endpoint, fanned out."""


class SourceSpec(BaseModel):
    """A source worth capturing on a schedule.

    Attributes:
        name: Stable identifier, used as the manifest key and directory name.
            Changing it starts a new history, so treat it as permanent.
        description: What the payload is.
        future_use: The named reason this source is captured. Required, and not
            decorative: a source without a concrete future use is storage and
            maintenance cost with no payoff, and should not be added.
        cadence: How often re-capture is worthwhile.
        kind: Which collector fetches it.
        url: Base or full URL, interpreted by the collector.
        params: Collector-specific settings (date field, page size, and so on).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(description="Stable identifier, e.g. 'sgu_groundwater'")
    description: str
    future_use: str = Field(description="Why this is captured; required by policy")
    cadence: Cadence
    kind: CollectorKind
    url: str
    params: dict[str, str | int] = Field(default_factory=dict)


class Observation(BaseModel):
    """One attempt to capture one source, successful or not.

    A failed attempt is recorded, not discarded. Gaps in the archive matter for
    interpreting it later, and silent failure is the main way a scheduled
    collector rots without anyone noticing.

    Attributes:
        source: ``SourceSpec.name``.
        captured_at: When the attempt ran (UTC). On success this is the
            ``known_at`` of every fact in the payload.
        ok: Whether a payload was retrieved.
        digest: SHA-256 of the payload, absent on failure.
        n_bytes: Uncompressed payload size, absent on failure.
        unchanged: True when the payload is byte-identical to this source's
            previous capture. The observation is still recorded (knowing a
            register did not change on a date is itself dated information) but
            no new blob is written.
        error: Failure reason, absent on success.
        meta: Collector-specific detail, e.g. records fetched, window covered.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str
    captured_at: datetime
    ok: bool
    digest: str | None = None
    n_bytes: int | None = None
    unchanged: bool = False
    error: str | None = None
    meta: dict[str, str | int] = Field(default_factory=dict)


class RunReport(BaseModel):
    """Result of one collector run across one or more sources."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    started_at: datetime
    observations: tuple[Observation, ...]

    @property
    def succeeded(self) -> tuple[Observation, ...]:
        """Observations that retrieved a payload."""
        return tuple(o for o in self.observations if o.ok)

    @property
    def failed(self) -> tuple[Observation, ...]:
        """Observations that did not retrieve a payload."""
        return tuple(o for o in self.observations if not o.ok)
