"""Write KEMI's hand-curated Swedish reevaluation announcements to JSONL.

No download or parsing step: `sources/kemi_reevaluations.py` is a small,
individually-verified, hand-curated fact list (KEMI publishes these as news
articles, not a structured export). Re-run `pipeline/03_build_graph.py`
afterward to merge this into the graph.

Usage:
    python pipeline/09_ingest_kemi_reevaluations.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pydantic import BaseModel

from hazium.sources.kemi_reevaluations import regulatory_events

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"


def _write_jsonl(path: Path, records: list[BaseModel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(record.model_dump_json() + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=PROCESSED)
    args = parser.parse_args()

    events = regulatory_events()
    print(f"KEMI reevaluation events: {len(events)}")
    for event in sorted(events, key=lambda e: e.substance_id):
        print(
            f"  {event.substance_id}: {event.kind.value} ({event.jurisdiction}, {event.event_date})"
        )

    _write_jsonl(args.out_dir / "kemi_reevaluations.jsonl", events)
    print(f"wrote {len(events)} events to {args.out_dir}/kemi_reevaluations.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
