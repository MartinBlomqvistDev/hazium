"""Fetch per-substance, per-year news-media volume from GDELT (DOC 2.0).

Scoped to the HEWB landmark set, not the full population: GDELT is an
independent *comparison/benchmark* axis and a present-day signal, never a model
feature (see `sources/gdelt.py`), so the bounded landmark set is what the
capability chart needs, and it keeps this inside the API's rate limit (one
request per substance, spaced above the 5-second floor). DOC 2.0 only indexes
from 2017, so the pre-2017 landmark stories are absent here by construction;
the site's pre-2017 public-controversy markers stay hand-curated.

Names are the canonical international spellings (GDELT is name-based; a
source-specific spelling like KEMI's "Propikonazol" returns nothing), keyed by
the same CAS the graph uses.

Usage:
    python pipeline/17_ingest_media_volume.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pydantic import BaseModel

from hazium.resolve.ids import safe_substance_node_id
from hazium.sources.gdelt import fetch_timeline, media_volume_records

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"
OUT_FILE = "media_volume.jsonl"

#: HEWB landmarks as (canonical international name, CAS). Names verified against
#: EU PPDB's international spellings; CAS matches the graph's substance ids.
LANDMARKS: tuple[tuple[str, str], ...] = (
    ("Clothianidin", "210880-92-5"),
    ("Thiamethoxam", "153719-23-4"),
    ("Imidacloprid", "138261-41-3"),
    ("Chlorpyrifos", "2921-88-2"),
    ("Chlorpyrifos-methyl", "5598-13-0"),
    ("Thiacloprid", "111988-49-9"),
    ("Epoxiconazole", "133855-98-8"),
    ("Mancozeb", "8018-01-7"),
    ("Dimethoate", "60-51-5"),
    ("Propiconazole", "60207-90-1"),
    ("Fluazinam", "79622-59-6"),
)


def _write_jsonl(path: Path, records: list[BaseModel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(record.model_dump_json() + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=PROCESSED)
    args = parser.parse_args()

    all_records = []
    for name, cas in LANDMARKS:
        substance_id = safe_substance_node_id(cas_number=cas, name=name)
        points = fetch_timeline(name)
        records = media_volume_records(substance_id, points)
        peak = max((r.volume for r in records), default=0.0)
        peak_year = max(records, key=lambda r: r.volume).year if records else None
        print(f"{name:22} {len(records):2} yrs (2017+)  peak {peak:.3f} in {peak_year}")
        all_records.extend(records)

    _write_jsonl(args.out_dir / OUT_FILE, all_records)
    print(f"\nwrote {len(all_records)} media-volume records to {args.out_dir}/{OUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
