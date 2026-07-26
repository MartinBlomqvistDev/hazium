"""Fetch molecular structures for the approved population from PubChem.

Separated from the screen that uses them because this step makes network calls
and the screen must not. Once this has run, `pipeline/35` is offline and
deterministic, and a reviewer can see exactly which structure each substance was
scored on rather than trusting whatever PubChem returns on the day they check.

Structures are timeless, so anything already resolved is never re-fetched.
Re-running this only picks up substances that are new to the population or that
PubChem failed to match last time.

Usage:
    python pipeline/34_ingest_structures.py
    python pipeline/34_ingest_structures.py --watchlist data/processed/survival_watchlist_h3.csv
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from hazium.sources.pubchem_structure import (
    fetch_all,
    load_structures,
    write_structures,
)

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"
#: Committed, not gitignored: a molecular formula is an immutable fact, and
#: keeping the snapshot in the repo is what lets `pipeline/35` run offline and
#: lets a reviewer see the exact structure each substance was scored on.
OUT = ROOT / "data" / "raw" / "pubchem_structures.jsonl"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--watchlist",
        type=Path,
        default=PROCESSED / "survival_watchlist_h3.csv",
        help="ranking CSV naming the approved population to fetch structures for",
    )
    args = parser.parse_args()

    if not args.watchlist.exists():
        raise SystemExit(f"missing {args.watchlist}; run pipeline/30 first")
    with args.watchlist.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    known = load_structures(OUT)
    wanted = [(r["substance_id"], r["name"]) for r in rows]
    todo = sum(1 for sid, _ in wanted if not (known.get(sid) and known[sid].resolved))
    print(f"population {len(wanted)}; cached {len(wanted) - todo}; fetching {todo}")

    records = fetch_all(wanted, known)
    # Keep anything previously fetched that is not in today's population, so the
    # cache accumulates rather than shrinking when the watchlist changes.
    merged = {**known, **{r.substance_id: r for r in records}}
    written = write_structures(OUT, merged.values())

    resolved = sum(1 for r in merged.values() if r.resolved)
    with_cf3 = sum(1 for r in merged.values() if r.has_cf3)
    odd = [r.substance_id for r in merged.values() if r.unexplained_fluorine]
    print(f"\nwrote {OUT.relative_to(ROOT)}: {written} records, {resolved} resolved")
    print(f"carrying a CF3 group: {with_cf3}")
    if odd:
        print(f"\n{len(odd)} with 3+ fluorines but no CF3 matched, worth an eye:")
        for sid in odd[:12]:
            record = merged[sid]
            print(f"   {record.molecular_formula:<24}{record.smiles}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
