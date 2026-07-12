"""Extract dated CLP hazard classifications from a pinned ECHA Annex VI
snapshot to JSONL.

echa.europa.eu sits behind an Azure WAF JS challenge that blocks automated
fetches, so this does not download anything: it reads a snapshot placed
manually into ``data/raw/annex_vi_clp_table_atp23_en.xlsx``. If it isn't
there yet, fetch it once from ``SOURCE_URL`` in a browser and save it to
that path.

Usage:
    python pipeline/05_ingest_clp.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import BaseModel

from hazium.sources.clp import DEFAULT_SNAPSHOT, SOURCE_URL, classifications_from, load

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"


def _write_jsonl(path: Path, records: list[BaseModel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(record.model_dump_json() + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=ROOT / DEFAULT_SNAPSHOT)
    parser.add_argument("--out-dir", type=Path, default=PROCESSED)
    args = parser.parse_args()

    if not args.snapshot.exists():
        print(
            f"missing snapshot: {args.snapshot}\n"
            f"fetch it manually (echa.europa.eu blocks automated requests):\n"
            f"  {SOURCE_URL}",
            file=sys.stderr,
        )
        return 1

    rows = load(args.snapshot)
    print(f"History sheet revisions parsed: {len(rows)}")

    classifications = classifications_from(rows)
    with_cas = sum(1 for c in classifications if "cas:" in c.substance_id)
    pre_2023 = sum(1 for c in classifications if c.known_at.year < 2023)
    print(
        f"hazard classifications: {len(classifications)} "
        f"({with_cas} CAS-resolved, {pre_2023} dated before 2023)"
    )
    _write_jsonl(args.out_dir / "clp_classifications.jsonl", classifications)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
