"""Adapter for Europe PMC scientific-literature volume, per substance per year.

Answers a question the rest of the ingested sources can't: what did the
independent scientific literature say about a substance *before* any
regulator acted on it? Every other source in this repository is downstream
of a regulatory or national process (EU PPDB approvals, ECHA CLP
classifications, EFSA assessments, KEMI's Swedish register); literature
volume is upstream of all of them -- see `SOURCE_ENHANCEMENT_SCOPE.md`'s
"governing idea" for why that ordering matters for early warning.

Europe PMC's REST API (`ebi.ac.uk/europepmc/webservices/rest`) is open,
unauthenticated, and unrestricted by any documented rate limit (verified
2026-07-18). No server-side year-faceting exists -- confirmed by reading the
reference R client's source, which issues two calls per year, ruled out at
population scale -- so this adapter instead issues one query per
(substance, hazard-filter) pair, paginated via `cursorMark`, bucketing each
hit's own `pubYear` client-side. Sorted newest-first so that if the page cap
is ever hit, the truncation drops the oldest years, not an arbitrary mix; in
practice this should not trigger -- even glyphosate (18,373 hits) and
chlorpyrifos (16,594) fit inside `MAX_PAGES`.

**The design this file implements was not the first one tried, and the
failures are recorded because they are easy to re-invent.** Raw hazard-hit
counts and self-relative hazard-fraction (a substance's own trend over time)
were both tested and both failed: Fluazinam, the project's anchor negative,
rose in lockstep with a genuine future EU non-renewal under both designs.
Population-relative *percentile* (a substance's hazard-fraction ranked
against a same-year cross-section), computed fresh at each cutoff and never
differenced across cutoffs, is what actually separates them -- and even that
took catching one more mistake: differencing the percentile itself across
two years reintroduces the same confound, because the comparison population's
own median drifts over time (a corpus-wide secular trend in how much
hazard/toxicology language appears in the literature generally). Full
numbers in the 2026-07-18 DEV_LOG entries; the percentile computation itself
lives in `ml/features.py`, not here -- this module only fetches and dates the
raw counts.

**Names must be canonical international names, never a source-specific
spelling.** Querying KEMI's Swedish register spelling "Propikonazol" returns
zero literature hits; the international name is "Propiconazole". Callers
must resolve a substance's name via the EU PPDB export (`sources/eu_ppdb.py`
already loads it) before calling this module, never pass a raw KEMI name.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from datetime import date

from hazium.models import LiteratureVolumeRecord

SOURCE = "europepmc"
BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
USER_AGENT = "hazium/0.1 (github.com/MartinBlomqvistDev/hazium)"

#: Validated 2026-07-18 (DEV_LOG): generic hazard/toxicology vocabulary,
#: deliberately not tailored to any one landmark case (that would be tuning
#: to the answer, the thing the baseline rule forbids).
HAZARD_TERMS = (
    'toxicity OR carcinogenic OR "endocrine disrupt" OR '
    '"reproductive toxicity" OR neurotoxicity OR genotoxic OR mutagenic'
)

#: Regulatory events in the graph reach back to 1996 (DEV_LOG, HEWB v1.1);
#: a few years of margin before that is enough context for any HEWB cutoff
#: (earliest 2009) without fetching decades of pre-regulatory-era noise.
MIN_YEAR = 1995
PAGE_SIZE = 1000
#: Generous: covers glyphosate (18,373 hits) and chlorpyrifos (16,594) whole,
#: the two heaviest hitters found while scoping this adapter.
MAX_PAGES = 25
REQUEST_DELAY_SECONDS = 0.4


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except Exception as e:  # noqa: BLE001 - retry any transient failure
            last_error = e
            time.sleep(2.0)
    raise RuntimeError(f"europepmc request failed after 3 attempts: {url}") from last_error


def _year_histogram(name: str, hazard_filter: bool, min_year: int = MIN_YEAR) -> dict[int, int]:
    """Every hit for ``name`` (optionally AND-filtered to hazard terms),
    bucketed by publication year via pagination -- see module docstring for
    why this replaces a naive one-query-per-year loop.
    """
    query = f'"{name}"'
    if hazard_filter:
        query += f" AND ({HAZARD_TERMS})"
    counts: dict[int, int] = {}
    cursor = "*"
    for _page in range(MAX_PAGES):
        params = {
            "query": query,
            "format": "json",
            "resultType": "lite",
            "pageSize": PAGE_SIZE,
            "sort": "P_PDATE_D desc",
            "cursorMark": cursor,
        }
        url = BASE_URL + "?" + urllib.parse.urlencode(params)
        data = _get_json(url)
        results = data.get("resultList", {}).get("result", [])
        for r in results:
            year_raw = r.get("pubYear")
            if not year_raw:
                continue
            year = int(year_raw)
            if year < min_year:
                continue
            counts[year] = counts.get(year, 0) + 1
        next_cursor = data.get("nextCursorMark")
        if not results or not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
        time.sleep(REQUEST_DELAY_SECONDS)
    return counts


def fetch_substance_year_counts(name: str) -> dict[int, tuple[int, int]]:
    """(hazard_count, total_count) per year for one substance's canonical name.

    Two full paginated fetches (total, then hazard-filtered) -- see module
    docstring on why the ratio, not either count alone, is the usable signal.
    """
    total = _year_histogram(name, hazard_filter=False)
    time.sleep(REQUEST_DELAY_SECONDS)
    hazard = _year_histogram(name, hazard_filter=True)
    time.sleep(REQUEST_DELAY_SECONDS)
    years = set(total) | set(hazard)
    return {y: (hazard.get(y, 0), total.get(y, 0)) for y in years}


def literature_volume_records(
    substance_id: str, year_counts: dict[int, tuple[int, int]]
) -> list[LiteratureVolumeRecord]:
    """Pure transform: fetched year-counts -> dated facts. No I/O."""
    return [
        LiteratureVolumeRecord(
            substance_id=substance_id,
            year=year,
            hazard_hit_count=hazard_count,
            total_hit_count=total_count,
            source=SOURCE,
            known_at=date(year + 1, 1, 1),
        )
        for year, (hazard_count, total_count) in year_counts.items()
    ]
