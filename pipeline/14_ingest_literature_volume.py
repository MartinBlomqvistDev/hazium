"""Fetch per-substance, per-year scientific-literature volume from Europe PMC.

Population is deliberately the EU PPDB export's substance list, not the full
graph -- see `SOURCE_ENHANCEMENT_SCOPE.md` and the 2026-07-18 DEV_LOG entry:
a substance can only ever receive the `NON_RENEWAL` positive label if it was
once EU-approved (the label comes from EU PPDB's own expiry date), so
literature signal for a substance outside that population is structurally
inert for this task, not merely more expensive to fetch.

Long-running (worst case low tens of minutes for ~1,100-1,482 substances,
each needing 2 paginated Europe PMC queries) and resumable by construction:
output is JSONL, already-fetched substance ids are read back from any
existing file and skipped, and each substance's records are flushed as soon
as they're fetched rather than held in memory until the end -- an
interruption partway through loses no completed work.

Usage:
    python pipeline/14_ingest_literature_volume.py
    python pipeline/14_ingest_literature_volume.py --limit 20   # smoke test
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

from hazium.resolve.ids import safe_substance_node_id
from hazium.sources.eu_ppdb import DEFAULT_EXPORT, load_export
from hazium.sources.europepmc import fetch_substance_year_counts, literature_volume_records

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"
OUT_FILE = "literature_volume.jsonl"
#: Tracks every substance *attempted*, independent of whether it produced any
#: records -- a substance with genuinely zero hits everywhere writes no JSONL
#: line, so resumability can't be derived from the JSONL alone or a
#: zero-hit substance would be re-fetched on every resume.
ATTEMPTED_FILE = "literature_volume_attempted.json"


def _load_attempted(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return set(json.loads(path.read_text(encoding="utf-8")))


def _save_attempted(path: Path, attempted: set[str]) -> None:
    path.write_text(json.dumps(sorted(attempted)), encoding="utf-8")


_CAS_RE = re.compile(r"^\d{2,7}-\d{2}-\d$")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", type=Path, default=ROOT / DEFAULT_EXPORT)
    parser.add_argument("--out-dir", type=Path, default=PROCESSED)
    parser.add_argument(
        "--limit", type=int, default=None, help="fetch only the first N (smoke test)"
    )
    args = parser.parse_args()

    if not args.export.exists():
        print(f"missing export: {args.export}", file=sys.stderr)
        return 1

    rows = load_export(args.export)
    # Clean CAS only: a malformed/absent CAS means no reliable identity to
    # query under, and (per the module docstring) no NON_RENEWAL is possible
    # without ever having appeared in this export with a real identity.
    population = [
        (r.name, r.cas_number) for r in rows if r.cas_number and _CAS_RE.match(r.cas_number)
    ]
    # de-dupe by substance id (a handful of names repeat across export rows)
    seen_ids: dict[str, tuple[str, str]] = {}
    for name, cas in population:
        sid = safe_substance_node_id(cas_number=cas, name=name)
        seen_ids.setdefault(sid, (name, cas))
    population = list(seen_ids.items())
    if args.limit:
        population = population[: args.limit]

    out_path = args.out_dir / OUT_FILE
    attempted_path = args.out_dir / ATTEMPTED_FILE
    out_path.parent.mkdir(parents=True, exist_ok=True)
    attempted = _load_attempted(attempted_path)
    todo = [(sid, name) for sid, (name, _cas) in population if sid not in attempted]

    print(f"population: {len(population)} substances with a clean CAS")
    print(f"already attempted: {len(attempted)}, remaining: {len(todo)}")

    start = time.monotonic()
    with out_path.open("a", encoding="utf-8") as f:
        for i, (substance_id, name) in enumerate(todo, start=1):
            try:
                year_counts = fetch_substance_year_counts(name)
            except Exception as e:  # noqa: BLE001 - one bad substance must not abort the run
                print(f"  [{i}/{len(todo)}] {name!r} FAILED: {e}", file=sys.stderr)
                continue
            records = literature_volume_records(substance_id, year_counts)
            for record in records:
                f.write(record.model_dump_json() + "\n")
            f.flush()
            attempted.add(substance_id)
            if i % 25 == 0 or i == len(todo):
                _save_attempted(attempted_path, attempted)
                elapsed = time.monotonic() - start
                rate = i / elapsed if elapsed else 0.0
                eta_min = (len(todo) - i) / rate / 60 if rate else float("nan")
                total_hits = sum(t for _h, t in year_counts.values())
                print(
                    f"  [{i}/{len(todo)}] {name!r}: {len(records)} years, "
                    f"{total_hits} total hits -- {rate:.2f}/s, ETA {eta_min:.1f} min"
                )

    print(f"wrote/updated {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
