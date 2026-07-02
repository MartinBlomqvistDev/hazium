"""Download KEMI annual sales reports and extract sales records to JSONL.

Each parsed figure is stamped with the publication date of the report it
came from. The same (substance, year) may appear in several reports; all
assertions are kept, because corrections are new facts, never mutations.

Usage:
    python pipeline/01_ingest_kemi_sales.py --years 2024
    python pipeline/01_ingest_kemi_sales.py --years 2020 2021 2022 2024
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.error import HTTPError

from hazium.sources.kemi import download_report, parse_sales_report

ROOT = Path(__file__).parent.parent
RAW_DIR = ROOT / "data" / "raw" / "kemi"
OUT_PATH = ROOT / "data" / "processed" / "kemi_sales.jsonl"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--years",
        type=int,
        nargs="+",
        default=[2024],
        help="report years to ingest (note: the 2023 report URL is irregular)",
    )
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    args = parser.parse_args()

    records = []
    for year in args.years:
        try:
            pdf_path = download_report(year, RAW_DIR)
        except HTTPError as err:
            print(f"{year}: download failed ({err.code}), skipping", file=sys.stderr)
            continue
        year_records = parse_sales_report(pdf_path)
        substances = {r.substance_id for r in year_records}
        print(f"{year}: {len(year_records)} records, {len(substances)} substances")
        records.extend(year_records)

    if not records:
        print("no records ingested", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(record.model_dump_json() + "\n")
    print(f"wrote {len(records)} records to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
