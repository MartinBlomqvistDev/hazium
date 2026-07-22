"""Payload retrieval, one function per ``CollectorKind``.

Every collector returns ``(payload, meta)``: the raw bytes to archive and a
small dict describing what was covered. ``meta`` is recorded in the manifest and
is what makes an incremental source resumable, since the next run reads the
previous window from it.

Payloads are normalised to newline-delimited JSON where a collector assembles
many responses, so a partial archive is still parseable and appending is cheap.
"""

from __future__ import annotations

import json
import time
import urllib.parse
from collections.abc import Callable
from datetime import date

from hazium.snapshots.fetch import FetchError, http_get
from hazium.snapshots.models import CollectorKind, SourceSpec

#: Politeness delay between requests when a collector fans out.
FANOUT_DELAY_SECONDS = 0.3

#: Page size for OGC API - Features requests.
OGC_PAGE_SIZE = 1000

#: Stop paging after this many pages, so a mis-specified filter cannot spin.
OGC_MAX_PAGES = 200

Fetcher = Callable[..., bytes]
Meta = dict[str, str | int]


def collect_file(spec: SourceSpec, *, fetch: Fetcher = http_get, **_: object) -> tuple[bytes, Meta]:
    """Retrieve a single-URL payload verbatim.

    Args:
        spec: Source specification; ``spec.url`` is fetched as-is.
        fetch: Injected HTTP getter.

    Returns:
        The raw body and a meta dict recording the URL.
    """
    payload = fetch(spec.url)
    return payload, {"url": spec.url}


def collect_ogc_features_window(
    spec: SourceSpec,
    *,
    since: date,
    fetch: Fetcher = http_get,
    sleep: Callable[[float], None] = time.sleep,
    max_pages: int = OGC_MAX_PAGES,
) -> tuple[bytes, Meta]:
    """Page an OGC API - Features collection over a rolling date window.

    Two decisions here are load-bearing, and both come from measuring the real
    source rather than assuming:

    **The window overlaps deliberately.** These registers publish results long
    after the sampling date: a 45-day window against SGU returned zero features
    while the same query from 2025-01-01 returned 58,179. Anchoring the window
    on the previous run would therefore drop every late-registered record. The
    window is wide and re-covers ground already seen; the store's content
    addressing absorbs the repetition.

    **Properties are projected.** A full SGU feature carries 90 properties at
    roughly 2.6 KB, so one capture of a two-year window would be about 150 MB.
    Keeping only the fields with a named downstream use (identity, date, CAS,
    value, unit, detection limits, geography) cuts that by an order of
    magnitude. Geometry is dropped for the same reason: the sampling point is
    identified by ``provplatsuuid`` and located by ``lanskod``, so coordinates
    add bulk with no join value. The full-fidelity dataset remains available as
    SGU's GeoPackage export if it is ever needed.

    Args:
        spec: Source spec. ``params`` must carry ``collection`` and
            ``date_field``; ``page_size`` and ``fields`` are optional, where
            ``fields`` is a comma-separated property allowlist.
        since: Inclusive lower bound applied to ``date_field``.
        fetch: Injected HTTP getter.
        sleep: Injected delay.
        max_pages: Safety cap on pagination.

    Returns:
        Newline-delimited projected records, and a meta dict recording the
        window, how many features were retrieved, and how many the server
        matched.
    """
    collection = str(spec.params["collection"])
    date_field = str(spec.params["date_field"])
    page_size = int(spec.params.get("page_size", OGC_PAGE_SIZE))
    raw_fields = str(spec.params.get("fields", "")).strip()
    keep = tuple(f.strip() for f in raw_fields.split(",") if f.strip())
    base = f"{spec.url.rstrip('/')}/collections/{collection}/items"
    cql = f"{date_field} >= DATE('{since.isoformat()}')"

    query = urllib.parse.urlencode({"f": "application/json", "limit": page_size, "filter": cql})
    url: str | None = f"{base}?{query}"

    records: list[str] = []
    matched: int | None = None
    for _page in range(max_pages):
        if url is None:
            break
        body = json.loads(fetch(url))
        if matched is None:
            matched = body.get("numberMatched")
        batch = body.get("features", [])
        for feature in batch:
            props = feature.get("properties", {})
            projected = {k: props.get(k) for k in keep} if keep else props
            records.append(json.dumps(projected, sort_keys=True))

        # Follow the server's own next link rather than constructing an offset.
        # This API silently ignores both `offset` and `startindex` and honours
        # only `startIndex`, so a hand-built offset returns page one forever and
        # fills the archive with duplicates. The next link cannot be got wrong.
        url = next(
            (link.get("href") for link in body.get("links", []) if link.get("rel") == "next"),
            None,
        )
        if not batch or len(batch) < page_size:
            break
        if matched is not None and len(records) >= matched:
            break
        sleep(FANOUT_DELAY_SECONDS)

    payload = "\n".join(records).encode("utf-8")
    meta: Meta = {
        "collection": collection,
        "since": since.isoformat(),
        "n_features": len(records),
    }
    if matched is not None:
        meta["number_matched"] = matched
    return payload, meta


def collect_ppdb_details(
    spec: SourceSpec,
    *,
    fetch: Fetcher = http_get,
    sleep: Callable[[float], None] = time.sleep,
    **_: object,
) -> tuple[bytes, Meta]:
    """Fan out over the EU Pesticides Database per-substance details endpoint.

    This is the collector that pays for the whole package. The EU PPDB bulk
    export carries Candidate-for-Substitution status, ADI, and classification
    with **no date anywhere**, which is why they were rejected as features (see
    DEV_LOG 2026-07-18, Tier 0a). They are undated because the register
    publishes current state only. Capturing the details endpoint on a schedule
    supplies the missing dates going forward: a value that appears in the March
    capture and not the February one changed in between.

    The endpoint is keyed by an opaque numeric id with no listing endpoint
    reachable by GET (``/search`` is POST-only), so ids are scanned over a range.

    **A miss is not an error here, which is the trap.** Requesting a
    nonexistent id (5000, 99999) returns HTTP 200 with a *truthy* payload whose
    ``basicDetails`` is an empty list. Testing the payload for truthiness
    therefore accepts every id ever requested, archives empty shells, and
    reports a perfect hit rate. Emptiness of ``basicDetails`` is the real
    signal, and ``n_missing`` is recorded so a scan that starts silently
    failing is visible in the manifest.

    The default range runs past the highest id observed in the bulk export
    (1577 as of 2026-07) with headroom, because a cap set to the current
    maximum silently drops every substance registered after it.

    Args:
        spec: Source spec. ``params`` may carry ``id_start``, ``id_end``.
        fetch: Injected HTTP getter.
        sleep: Injected delay.

    Returns:
        Newline-delimited ``{"id": ..., "payload": ...}`` records, and a meta
        dict recording the scanned range, hits, and misses.
    """
    id_start = int(spec.params.get("id_start", 1))
    id_end = int(spec.params.get("id_end", 1800))

    lines: list[str] = []
    hits = 0
    misses = 0
    non_public = 0
    for substance_id in range(id_start, id_end + 1):
        url = f"{spec.url.rstrip('/')}/{substance_id}"
        try:
            body = json.loads(fetch(url))
        except (FetchError, ValueError):
            misses += 1
            continue
        payload = body.get("payload")
        if not _is_real_substance(payload):
            misses += 1
            continue
        if not _is_public(payload):
            non_public += 1
            sleep(FANOUT_DELAY_SECONDS)
            continue
        hits += 1
        lines.append(json.dumps({"id": substance_id, "payload": payload}, sort_keys=True))
        sleep(FANOUT_DELAY_SECONDS)

    return (
        "\n".join(lines).encode("utf-8"),
        {
            "id_start": id_start,
            "id_end": id_end,
            "n_substances": hits,
            "n_missing": misses,
            "n_non_public": non_public,
        },
    )


def _is_real_substance(payload: object) -> bool:
    """Whether a details payload describes an actual substance.

    The endpoint answers 200 with an empty ``basicDetails`` for unknown ids, so
    presence of the payload proves nothing.
    """
    return bool(isinstance(payload, dict) and payload.get("basicDetails"))


def _is_public(payload: dict) -> bool:
    """Whether the register publishes this substance.

    Scanning ids reaches records the official search does not return: 87 of the
    100 such records carry ``AS_PUBLIC = "0"``, meaning the register
    deliberately withholds them. They are excluded rather than archived. This
    archive is intended to be shareable, and republishing records a source has
    flagged as not for publication is not defensible merely because an id scan
    can reach them. The count is reported as ``n_non_public`` so their existence
    stays visible without their content being retained.
    """
    details = payload.get("basicDetails")
    if isinstance(details, list):
        details = details[0] if details else {}
    if not isinstance(details, dict):
        return True
    return str(details.get("AS_PUBLIC", "1")).strip() == "1"


#: Dispatch table, keyed by the spec's declared kind.
COLLECTORS: dict[CollectorKind, Callable[..., tuple[bytes, Meta]]] = {
    CollectorKind.FILE: collect_file,
    CollectorKind.OGC_FEATURES_WINDOW: collect_ogc_features_window,
    CollectorKind.PPDB_DETAILS: collect_ppdb_details,
}
