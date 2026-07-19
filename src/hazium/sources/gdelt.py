"""Adapter for GDELT news-media attention volume, per substance per year.

GDELT (`gdeltproject.org`) monitors global news media and its DOC 2.0 API
returns, for a query, a timeline of *coverage intensity*: the share of all
monitored news matching the query, normalised against total news volume so it
is comparable across years. This is the "when did the story break" signal the
regulatory and hazard sources cannot give: independent of the regulatory
funnel, driven by public and journalistic attention.

**Access is rate-limited, not blocked.** The DOC API returns a plain-text
"limit requests to one every 5 seconds" notice instead of JSON when hit too
fast (verified 2026-07-19: rapid calls get HTTP 429; a single call, or calls
spaced with backoff, return JSON). This adapter therefore retries on 429 with
a delay above the published 5-second floor, the same politeness discipline
`europepmc.py` already uses. An earlier note that GDELT was "blocked" was
wrong and is corrected here.

**Coverage floor: 2017-01-01.** DOC 2.0's fulltext index begins in 2017
(verified against the live API: a `timespan=full` query for chlorpyrifos runs
2017-01-01 to present). Pre-2017 attention is absent, not zero. For the
historical HEWB landmarks this means the pre-2017 public build-up is invisible
here, so it is not the source for those markers; GDELT's value is the
present-day watchlist and the 2017+ tail. The deeper GDELT GKG (2013+) and raw
event files (1979+) exist but require BigQuery or terabyte-scale downloads,
out of scope for this adapter.

**Names must be canonical international names**, resolved via the EU PPDB
export like `europepmc.py`, never a source-specific spelling.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from collections import defaultdict

from hazium.models import MediaVolumeRecord

SOURCE = "gdelt:doc"
BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
USER_AGENT = "hazium/0.1 (github.com/MartinBlomqvistDev/hazium; research)"

#: DOC 2.0's fulltext index begins here; earlier years carry no data.
MIN_YEAR = 2017
#: Above the published one-request-per-5-seconds floor, with headroom.
REQUEST_DELAY_SECONDS = 6.0
MAX_RETRIES = 5


def _get_json(url: str) -> dict | None:
    """Fetch GDELT JSON, retrying past the rate-limit notice.

    A rate-limited response is not an HTTP error in every case: GDELT may
    return HTTP 429, or a 200 whose body is the plain-text limit notice rather
    than JSON. Both are treated as retryable; anything that parses as JSON is
    returned. ``None`` after exhausting retries, so a single stubborn
    substance degrades the fetch rather than aborting it.
    """
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for _attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                raw = resp.read().decode("utf-8", "replace")
            if raw.lstrip().startswith("{"):
                return json.loads(raw)
        except Exception:  # noqa: BLE001 - 429s and transient network errors alike
            pass
        time.sleep(REQUEST_DELAY_SECONDS)
    return None


def fetch_timeline(name: str) -> list[tuple[str, float]]:
    """Raw (date, volume) points for one substance's canonical name.

    Empty list on a substance GDELT has no coverage for, or on a fetch that
    never got past the rate limit. Pure I/O; annual bucketing is
    ``media_volume_records``'s job.
    """
    params = {
        "query": f'"{name}"',
        "mode": "timelinevol",
        "format": "json",
        "timespan": "full",
    }
    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    data = _get_json(url)
    if not data:
        return []
    timeline = data.get("timeline", [])
    if not timeline:
        return []
    return [(p["date"], float(p["value"])) for p in timeline[0].get("data", [])]


def media_volume_records(
    substance_id: str, points: list[tuple[str, float]], min_year: int = MIN_YEAR
) -> list[MediaVolumeRecord]:
    """Pure transform: dated volume points -> annual mean-volume facts.

    Each GDELT point is stamped ``YYYYMMDDThhmmssZ``; the year is its first
    four characters. Years below ``min_year`` are dropped (outside DOC's
    index), and a year with no points produces no record, so absence of
    coverage never reads as a real zero. ``known_at`` is Jan 1 of ``year + 1``.
    """
    from datetime import date

    by_year: dict[int, list[float]] = defaultdict(list)
    for date_str, value in points:
        year = int(date_str[:4])
        if year < min_year:
            continue
        by_year[year].append(value)
    return [
        MediaVolumeRecord(
            substance_id=substance_id,
            year=year,
            volume=sum(values) / len(values),
            source=SOURCE,
            known_at=date(year + 1, 1, 1),
        )
        for year, values in sorted(by_year.items())
    ]
