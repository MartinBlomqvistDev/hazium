"""Download EFSA's OpenFoodTox export and extract substances, degradation
links, and dated scientific assessments to JSONL.

This is the first source with genuinely dated evidence (each assessment
carries the EFSA opinion's real evaluation date), rather than a live-register
snapshot. See ``sources/openfoodtox.py`` for the temporal caveats on the
degradation links, which are not per-row dated.

Usage:
    python pipeline/04_ingest_openfoodtox.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pydantic import BaseModel

from hazium.sources.openfoodtox import (
    assessments_from,
    degradation_links_from,
    download_export,
    load,
    record_publication_date,
    substances_from,
)

ROOT = Path(__file__).parent.parent
RAW_DIR = ROOT / "data" / "raw" / "openfoodtox"
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

    xlsx_path = download_export(RAW_DIR)
    published = record_publication_date()
    print(f"OpenFoodTox 3.0 export published: {published}")
    index = load(xlsx_path)

    substances = substances_from(index, known_at=published)
    with_cas = sum(1 for s in substances if s.cas_number)
    print(f"substances: {len(substances)} ({with_cas} with CAS)")
    _write_jsonl(args.out_dir / "openfoodtox_substances.jsonl", substances)

    links = degradation_links_from(index, known_at=published)
    print(f"degradation links: {len(links)}")
    _write_jsonl(args.out_dir / "openfoodtox_degradation.jsonl", links)

    documents = assessments_from(index)
    dated_before_2023 = sum(1 for d in documents if d.known_at.year < 2023)
    print(f"dated EFSA assessments: {len(documents)} ({dated_before_2023} before 2023)")
    _write_jsonl(args.out_dir / "openfoodtox_assessments.jsonl", documents)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
