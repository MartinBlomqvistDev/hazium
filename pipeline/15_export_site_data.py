"""Export a small, self-contained JSON of HEWB results for the public site.

The site (`web/`) is a static Next.js app with no backend and no access to
`data/processed/` (gitignored, local-only) at Vercel build time, so this is
the one deliberate bridge: a small, human-readable, committed JSON built from
the same HEWB CSVs `pipeline/12_run_hewb.py` writes. Re-run this after any
HEWB rerun (e.g. once the Tier-1 literature feature lands and HEWB moves to
v1.2) and commit the updated `web/data/hewb.json` -- the site never reads
`data/processed/` directly.

Usage:
    python pipeline/15_export_site_data.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from hazium.benchmark.hewb import LANDMARK_CASES

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"
SITE_DATA = ROOT / "web" / "data" / "hewb.json"

VARIANT = "headline"
K_VALUES = (10, 20, 50)


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main() -> int:
    from hazium.benchmark.hewb import HEWB_VERSION

    lead_times_rows = [r for r in _read_csv(PROCESSED / "hewb_lead_times.csv") if r["variant"] == VARIANT]
    aggregate_rows = [r for r in _read_csv(PROCESSED / "hewb_aggregate.csv") if r["variant"] == VARIANT]

    landmarks = []
    for case in LANDMARK_CASES:
        rows = {int(r["k"]): r for r in lead_times_rows if r["case"] == case.name}
        if not rows:
            continue  # early_warning-only cases (none currently) skip the headline export
        any_row = next(iter(rows.values()))
        lead = {}
        for k in K_VALUES:
            r = rows.get(k)
            if r and r["lead_time_months"]:
                lead[str(k)] = int(r["lead_time_months"])
            else:
                lead[str(k)] = None
        flagged = any(v is not None for v in lead.values())
        landmarks.append(
            {
                "name": case.name,
                "cas": case.cas,
                "note": case.note,
                "action_date": any_row["action_date"],
                "flagged": flagged,
                "lead_time_months": lead,
            }
        )

    flagged_count = sum(1 for lm in landmarks if lm["flagged"])
    best_lead = max(
        (lm["lead_time_months"]["10"] for lm in landmarks if lm["lead_time_months"]["10"]),
        default=None,
    )
    best_case = next(
        (lm["name"] for lm in landmarks if lm["lead_time_months"]["10"] == best_lead), None
    )

    # per-cutoff xgboost vs best-trivial AP, for the aggregate chart
    by_cutoff: dict[str, dict[str, float]] = {}
    for r in aggregate_rows:
        by_cutoff.setdefault(r["cutoff"], {})[r["model"]] = float(r["average_precision"])
    aggregate = []
    for cutoff in sorted(by_cutoff):
        models = by_cutoff[cutoff]
        xgb = models.get("xgboost")
        if xgb is None:
            continue
        trivial = max(v for m, v in models.items() if m != "xgboost")
        aggregate.append({"cutoff": cutoff, "xgboost_ap": xgb, "best_trivial_ap": trivial})

    payload = {
        "hewb_version": HEWB_VERSION,
        "provisional": True,
        "provisional_note": (
            "These are HEWB v1.1 numbers (tabular features only). A literature-volume "
            "feature (Tier 1) is being added and may move these numbers to v1.2 -- "
            "re-export after that run lands."
        ),
        "headline": {
            "landmarks_flagged": flagged_count,
            "landmarks_total": len(landmarks),
            "best_lead_time_months": best_lead,
            "best_lead_time_case": best_case,
        },
        "landmarks": landmarks,
        "aggregate": aggregate,
    }

    SITE_DATA.parent.mkdir(parents=True, exist_ok=True)
    SITE_DATA.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {SITE_DATA} ({len(landmarks)} landmarks, {len(aggregate)} cutoffs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
