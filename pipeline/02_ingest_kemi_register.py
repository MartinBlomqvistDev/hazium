"""Snapshot KEMI's pesticide register: substances with CAS, and all products.

Writes two JSONL files stamped with the snapshot date. Re-running on a later
date produces new facts alongside the old, never replacements.

Usage:
    python pipeline/02_ingest_kemi_register.py
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from pydantic import BaseModel

from hazium.sources.kemi_register import fetch_products, fetch_substances

ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "data" / "processed"


def _write_jsonl(path: Path, records: list[BaseModel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(record.model_dump_json() + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    snapshot = date.today()

    substances = fetch_substances(known_at=snapshot)
    with_cas = sum(1 for s in substances if s.cas_number)
    print(f"substances: {len(substances)} ({with_cas} with CAS)")
    _write_jsonl(args.out_dir / "kemi_register_substances.jsonl", substances)

    products = fetch_products(known_at=snapshot)
    approved = sum(1 for p in products if p.approved)
    print(f"products: {len(products)} ({approved} currently approved)")
    _write_jsonl(args.out_dir / "kemi_register_products.jsonl", products)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
