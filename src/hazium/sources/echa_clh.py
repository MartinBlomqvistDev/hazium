"""Adapter for ECHA CLH (harmonised classification) intentions, per substance.

The ECHA "Registry of CLH intentions until outcome" records every substance for
which a harmonised classification proposal has been made, with the dates of
each step. The *intention* date is an in-funnel regulatory signal that precedes
the Annex VI classification (already ingested by `clp.py`) by one to three
years. See `SOURCE_ENHANCEMENT_SCOPE.md` Tier 2.

**This adapter parses a committed snapshot, it does not fetch live**, and the
reason is a hard access fact verified 2026-07-19: ECHA's registry
(`echa.europa.eu` and `poisoncentres.echa.europa.eu`) sits behind an Azure WAF
that returns HTTP 403 to any programmatic client; only an interactive browser
clears the challenge. The registry has no API or bulk export. So the pesticide
subset was acquired once, browser-assisted, by bucketing the registry's
receipt-date filter year by year (the dossier receipt date; the finer "date of
intention" is a few months earlier and lives on per-substance detail pages),
and written to `data/raw/clh_intentions_ppp.jsonl`. That file is the source of
record here; refreshing it is a manual browser step, not a pipeline run. This
is an honest limitation, documented rather than hidden: a WAF-gated,
browser-only source cannot be a self-refreshing feed.

Names are irrelevant here (unlike the literature/media adapters): the registry
is CAS-keyed, so identity joins the graph spine cleanly with no synonym risk.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from hazium.models import CLHIntentionRecord

SOURCE = "echa:clh_intentions"
DEFAULT_SNAPSHOT = Path("data/raw/clh_intentions_ppp.jsonl")


def earliest_intention_year(snapshot_path: Path) -> dict[str, int]:
    """Earliest CLH-intention receipt year per CAS, from the snapshot.

    A substance can carry more than one intention over time (an original
    classification and a later revision); the *earliest* is the one that
    matters as an early-warning signal, so years are min-reduced per CAS. Pure
    over the file's contents.
    """
    earliest: dict[str, int] = {}
    with snapshot_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            year = int(row["receipt_year"])
            for cas in row["cas"]:
                if cas not in earliest or year < earliest[cas]:
                    earliest[cas] = year
    return earliest


def clh_intention_records(earliest_by_cas: dict[str, int]) -> list[CLHIntentionRecord]:
    """Pure transform: earliest-year-per-CAS map -> dated facts.

    ``known_at`` is Jan 1 of ``year + 1`` (only year granularity is known, so
    the fact is conservatively dated to when it was provably public: year end).
    The substance id is the CAS-keyed graph id directly (``substance:cas:{cas}``,
    the form ``substance_node_id`` produces for a CAS-identified substance), so
    these join the population by CAS; a snapshot CAS with no matching population
    node simply contributes no feature.
    """
    return [
        CLHIntentionRecord(
            substance_id=f"substance:cas:{cas}",
            intention_year=year,
            source=SOURCE,
            known_at=date(year + 1, 1, 1),
        )
        for cas, year in earliest_by_cas.items()
    ]
