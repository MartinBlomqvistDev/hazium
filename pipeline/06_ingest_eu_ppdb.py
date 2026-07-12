"""Extract EU regulatory events from the EU Pesticides Database bulk export.

Reads the site's "Export Active substances" XLSX (placed in `data/raw/`) and
emits dated `RegulatoryEvent` facts: EU approvals and non-renewals. The
non-renewals are V1's regulatory-action label. Richer per-act history and
member-state authorisations live behind the `/details/{id}` API (see
`sources/eu_ppdb.py`) and are a documented future enrichment, not needed here.

Usage:
    python pipeline/06_ingest_eu_ppdb.py
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from pydantic import BaseModel

from hazium.models import RegulatoryEventKind
from hazium.sources.eu_ppdb import DEFAULT_EXPORT, load_export, regulatory_events_from

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"


def _write_jsonl(path: Path, records: list[BaseModel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(record.model_dump_json() + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", type=Path, default=ROOT / DEFAULT_EXPORT)
    parser.add_argument("--out-dir", type=Path, default=PROCESSED)
    args = parser.parse_args()

    if not args.export.exists():
        print(
            f"missing export: {args.export}\n"
            "download it from the EU Pesticides Database "
            "('Export Active substances' button) into data/raw/",
            file=sys.stderr,
        )
        return 1

    rows = load_export(args.export)
    statuses = Counter(r.status for r in rows)
    print(f"active substances: {len(rows)} {dict(statuses)}")

    events = regulatory_events_from(rows)
    kinds = Counter(e.kind for e in events)
    print(f"regulatory events: {len(events)}")
    for kind, n in kinds.items():
        print(f"  {kind.value}: {n}")

    non_renewals = [e for e in events if e.kind == RegulatoryEventKind.NON_RENEWAL]
    print("non-renewal positive class by cutoff (the V1 label):")
    for year in (2018, 2020, 2022, 2023, 2024):
        after = sum(1 for e in non_renewals if e.event_date >= date(year, 1, 1))
        print(f"  non-renewals dated >= {year}-01-01: {after}")

    _write_jsonl(args.out_dir / "eu_ppdb_events.jsonl", events)
    print(f"wrote {len(events)} events to {args.out_dir}/eu_ppdb_events.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
