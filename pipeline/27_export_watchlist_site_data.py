"""Export the forward watchlist, its crop exposure and its resolution calendar.

The site is a static build with no access to ``data/processed/``, which is
gitignored, so this is the bridge: the CSVs written by `pipeline/13`, `25` and
`26` become one small committed JSON under ``web/data/``.

Everything else on the site is retrospective. This is the one surface making a
claim about a future that has not happened, so two things are carried alongside
the numbers rather than left to the copy:

**Each substance's approval expiry.** That date is when the Commission is
forced to decide, which is what turns a ranking into a falsifiable claim with a
deadline instead of an open-ended assertion.

**No product or brand names.** The crop is the finest granularity published. At
an average precision around 0.25 most of these substances will not be actioned,
and attaching named commercial products to a mostly-wrong list would be both
unfair and legally exposed. Counts by crop carry the same information without
naming anyone.

Usage:
    python pipeline/27_export_watchlist_site_data.py
"""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"
SITE_DATA = ROOT / "web" / "data" / "watchlist.json"

VARIANT = "headline"

#: How many watchlist ranks to publish. Precision holds a plateau to about k=50
#: on cutoffs old enough to have resolved (0.68-0.78) and is still 0.57-0.62 at
#: k=100, while recall roughly doubles, so the exposure map uses the wider band.
TOP = 100

#: Crops shown on the site. The register's catch-all labels ("fruit
#: (unspecified)", "berries (unspecified)") are real but say little, so they are
#: dropped here rather than padding a table a reader is meant to scan.
CROP_EXCLUDE = frozenset({"fruit (unspecified)", "berries (unspecified)", "cereals (unspecified)"})

#: Crops needing at least this many approved products before they are shown. A
#: crop with three products cannot support a percentage anyone should read.
MIN_PRODUCTS = 10


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"missing {path}; run the pipeline that writes it first")
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main() -> int:
    watchlist = _read_csv(PROCESSED / f"current_watchlist_{VARIANT}.csv")[:TOP]
    crops = _read_csv(PROCESSED / f"crop_exposure_{VARIANT}.csv")
    by_substance = _read_csv(PROCESSED / f"crop_exposure_{VARIANT}_by_substance.csv")
    resolution = _read_csv(PROCESSED / f"resolution_{VARIANT}.csv")

    crops_of = {r["substance"]: r["crops"] for r in by_substance}
    expiry_of = {r["substance"]: r["baseline_expiry"] for r in resolution}
    outcome_of = {r["substance"]: r["outcome"] for r in resolution}

    entries = []
    for row in watchlist:
        name = row["name"]
        crop_list = [c.strip() for c in (crops_of.get(name) or "").split(";") if c.strip()]
        entries.append(
            {
                "rank": int(row["rank"]),
                "name": name,
                "in_sweden": row["in_kemi_sweden_register"] == "True",
                "crops": crop_list,
                "expiry": expiry_of.get(name) or None,
                "outcome": outcome_of.get(name) or "untracked",
            }
        )

    crop_rows = [
        {
            "crop": r["crop"],
            "products": int(r["approved_products"]),
            "flagged": int(r["products_with_watchlist_substance"]),
            "percent": int(r["percent"]),
        }
        for r in crops
        if r["crop"] not in CROP_EXCLUDE and int(r["approved_products"]) >= MIN_PRODUCTS
    ]

    # Resolution calendar: how many entries reach a forced decision, by year.
    dated = sorted(e["expiry"] for e in entries if e["expiry"])
    calendar: list[dict[str, int]] = []
    running = 0
    for year in sorted({int(d[:4]) for d in dated}):
        count = sum(1 for d in dated if int(d[:4]) == year)
        running += count
        calendar.append({"year": year, "count": count, "cumulative": running})

    # The base rate must come from distinct products, not from summing the
    # per-crop table: a product approved for wheat, barley and rye sits in three
    # rows, so the columns cannot be added. Here the wrong method landed close
    # (35% against 37%) because the double-counting is spread fairly evenly, but
    # that is luck rather than a reason to keep it: the error scales with how
    # much crop overlap the register happens to carry.
    summary = _read_csv(PROCESSED / f"crop_exposure_{VARIANT}_summary.csv")[0]
    with_crop = int(summary["products_with_a_crop"])
    flagged = int(summary["products_with_watchlist_substance"])

    payload = {
        "variant": VARIANT,
        "generated": date.today().isoformat(),
        "top": TOP,
        "tracked": len(dated),
        "on_market": sum(1 for e in entries if e["crops"]),
        "calendar": calendar,
        "crops": crop_rows,
        "entries": [e for e in entries if e["crops"] or e["expiry"]],
        "base_rate_percent": round(flagged / with_crop * 100) if with_crop else 0,
    }

    SITE_DATA.parent.mkdir(parents=True, exist_ok=True)
    SITE_DATA.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"watchlist entries published: {len(payload['entries'])} of top {TOP}")
    print(f"with a Swedish crop use:     {payload['on_market']}")
    print(f"with a dated expiry:         {payload['tracked']}")
    print(f"crops shown:                 {len(crop_rows)}")
    print("\nresolution calendar:")
    for row in calendar[:6]:
        print(f"  {row['year']}  {row['count']:>3} decided   cumulative {row['cumulative']:>3}")
    print(f"\nwrote {SITE_DATA.relative_to(ROOT)} ({SITE_DATA.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
