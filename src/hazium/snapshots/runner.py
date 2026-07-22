"""Orchestration: run collectors, isolate failures, decide when to alert.

Two behaviours here are the difference between a collector that survives years
of unattended running and one that quietly rots:

* **Failure isolation.** One dead source must not abort the run. Every source is
  attempted, and failures are recorded rather than raised.
* **Alert on persistence, not on incident.** A single failed fetch is usually a
  transient outage and alerting on it trains the reader to ignore alerts. A
  source that has failed several runs in a row has actually broken, most often
  because a schema or URL changed, and that must surface.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime, timedelta

from hazium.snapshots.collectors import COLLECTORS
from hazium.snapshots.fetch import http_get
from hazium.snapshots.models import CollectorKind, Observation, RunReport, SourceSpec
from hazium.snapshots.store import SnapshotStore

#: Consecutive failures before a source is treated as broken rather than flaky.
FAILURE_ALERT_THRESHOLD = 3

#: Rolling window for date-windowed sources, in days.
#:
#: Wide on purpose. These registers publish results long after the sampling
#: date: a 45-day window against SGU returned zero features, while the same
#: query from 2025-01-01 returned 58,179. A high-water mark anchored on the
#: previous run would therefore drop every late-registered record. Overlapping
#: captures are the correct trade, and field projection plus content addressing
#: keep the cost of that overlap small.
WINDOW_DAYS = 730


def window_start(
    spec: SourceSpec,
    *,
    today: date | None = None,
    window_days: int = WINDOW_DAYS,
) -> date:
    """Lower bound for a date-windowed capture of ``spec``.

    Always a fixed rolling window back from today, never a high-water mark
    resumed from the previous run. See ``WINDOW_DAYS`` for why.

    Args:
        spec: The windowed source; ``params['window_days']`` overrides the
            default when a source needs a different span.
        today: Injected for tests.
        window_days: Default span when the spec does not set one.

    Returns:
        Inclusive start date for the capture window.
    """
    span = int(spec.params.get("window_days", window_days))
    base = today or datetime.now(UTC).date()
    return base - timedelta(days=span)


def run_sources(
    specs: Iterable[SourceSpec],
    store: SnapshotStore,
    *,
    fetch: Callable[..., bytes] = http_get,
    sleep: Callable[[float], None] = time.sleep,
    today: date | None = None,
) -> RunReport:
    """Capture each source, recording one observation per attempt.

    Args:
        specs: Sources to capture.
        store: Destination store.
        fetch: Injected HTTP getter, threaded through to collectors.
        sleep: Injected delay.
        today: Injected for tests.

    Returns:
        A report covering every attempted source.
    """
    started = datetime.now(UTC)
    observations: list[Observation] = []

    for spec in specs:
        collector = COLLECTORS[spec.kind]
        kwargs: dict[str, object] = {"fetch": fetch, "sleep": sleep}
        if spec.kind is CollectorKind.OGC_FEATURES_WINDOW:
            kwargs["since"] = window_start(spec, today=today)
        try:
            payload, meta = collector(spec, **kwargs)
        except Exception as exc:  # noqa: BLE001 - one bad source must not abort the run
            observations.append(store.record_failure(spec.name, f"{type(exc).__name__}: {exc}"))
            continue
        observations.append(store.record_success(spec.name, payload, meta=meta))

    return RunReport(started_at=started, observations=tuple(observations))


def broken_sources(
    store: SnapshotStore,
    specs: Iterable[SourceSpec],
    *,
    threshold: int = FAILURE_ALERT_THRESHOLD,
) -> list[str]:
    """Names of sources that have failed ``threshold`` or more runs in a row."""
    return [s.name for s in specs if store.consecutive_failures(s.name) >= threshold]


def exit_code(
    report: RunReport,
    store: SnapshotStore,
    specs: Iterable[SourceSpec],
    *,
    threshold: int = FAILURE_ALERT_THRESHOLD,
) -> int:
    """Process exit status for a run.

    Non-zero only when something needs a human: every source failed (which
    usually means the network or the runner itself, not the sources), or some
    source has failed persistently enough to be considered broken. A single
    transient failure returns 0 deliberately, so routine outages do not train
    the reader to ignore a red run.

    Returns:
        0 when healthy, 1 when attention is needed.
    """
    specs = list(specs)
    if report.observations and not report.succeeded:
        return 1
    if broken_sources(store, specs, threshold=threshold):
        return 1
    return 0
