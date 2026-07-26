"""Export the v2 survival result for the site to read.

The site used to hardcode these numbers in JSX. That is how it came to be
showing 374 tests against 385, and an average precision that had moved twice
since the copy was written. A page that quotes a result should read it from the
run that produced it, so this is the bridge: the CSVs and the verification JSON
become one small committed file under ``web/data/``.

Nothing is computed here. If a number looks wrong, the fix belongs in
`pipeline/28` or `pipeline/32`, not in this file and never in the component.

Usage:
    python pipeline/33_export_survival_site_data.py
"""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"
SITE_DATA = ROOT / "web" / "data" / "survival.json"

ARMS = ("age only", "evidence only", "age + evidence")

#: The forward split the site quotes. Fitted through 2019 and scored on
#: everything after, it is the one with enough test events on both sides of the
#: 2017-2021 renewal wave to be worth a reader's attention.
QUOTED_SPLIT = "2019"


def _sections(path: Path) -> list[list[list[str]]]:
    """Split a stacked result CSV into its blank-line-separated sections."""
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    sections: list[list[list[str]]] = [[]]
    for row in rows:
        if not row:
            sections.append([])
            continue
        sections[-1].append(row)
    return [s for s in sections if s]


def _arms(path: Path) -> dict[str, dict[str, float]]:
    head, *_ = _sections(path)
    return {
        row[0]: {
            "average_precision": float(row[1]),
            "seed_sd": float(row[2]),
            "auc": float(row[3]),
            "lift": float(row[4]),
        }
        for row in head[1:]
        if row[0] in ARMS
    }


def _named_deltas(path: Path, header: str) -> dict[str, float]:
    for section in _sections(path):
        if section[0][0] == header:
            return {row[0]: float(row[2]) for row in section[1:]}
    return {}


def _forward(path: Path) -> list[dict[str, float]]:
    for section in _sections(path):
        if section[0][0] == "train_through":
            return [
                {
                    "train_through": int(row[0]),
                    "train_events": int(row[1]),
                    "test_events": int(row[2]),
                    "age_ap": float(row[3]),
                    "both_ap": float(row[4]),
                    "age_hits_at_50": int(row[5]),
                    "both_hits_at_50": int(row[6]),
                }
                for row in section[1:]
            ]
    return []


def main() -> int:
    h1 = PROCESSED / "survival_h1.csv"
    h3 = PROCESSED / "survival_h3.csv"
    checks_path = PROCESSED / "survival_verification_h1.json"
    for path in (h1, h3, checks_path):
        if not path.exists():
            raise SystemExit(f"missing {path}; run pipeline/28 (both horizons) and 32 first")

    checks = json.loads(checks_path.read_text(encoding="utf-8"))
    forward = _forward(h1)
    quoted = next(r for r in forward if str(r["train_through"]) == QUOTED_SPLIT)
    cohort = checks["anchor_cohort"]

    payload = {
        "generated": date.today().isoformat(),
        "version": "2.1",
        "horizon_1": {
            "arms": _arms(h1),
            "groups": _named_deltas(h1, "group_added_to_age"),
            "blocks": _named_deltas(h1, "evidence_block_added_to_age"),
            "forward": forward,
            "quoted_split": quoted,
            "positive_splits": sum(1 for r in forward if r["both_ap"] > r["age_ap"]),
            "total_splits": len(forward),
        },
        "horizon_3": {
            "arms": _arms(h3),
            "groups": _named_deltas(h3, "group_added_to_age"),
            "blocks": _named_deltas(h3, "evidence_block_added_to_age"),
            "positive_splits": sum(1 for r in _forward(h3) if r["both_ap"] > r["age_ap"]),
            "total_splits": len(_forward(h3)),
        },
        "verification": {
            "age_from_evidence_r2": checks["age_from_evidence_r2"]["grouped_by_substance"],
            "permutation_p": checks["permutation"]["p"],
            "lag_deltas": checks["lag_deltas"],
            "linear_share_recovered": checks["linear"]["share_recovered"],
            "calibration": checks["calibration"],
        },
        "anchor_cohort": {
            "population": cohort["population"],
            "size": len(cohort["ranks"]),
            "ranks": cohort["ranks"],
            "names": cohort["names"],
            "top_k": cohort["top_k"],
            "hits_in_top_k": cohort["hits_in_top_k"],
            "expected_in_top_k": round(cohort["expected_in_top_k"], 1),
            "median_rank": cohort["median_rank"],
            "median_percentile": round(cohort["median_percentile"], 3),
            "detected": cohort["hits_in_top_k"] > cohort["expected_in_top_k"],
        },
    }

    SITE_DATA.parent.mkdir(parents=True, exist_ok=True)
    SITE_DATA.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")

    both = payload["horizon_1"]["arms"]["age + evidence"]["average_precision"]
    age = payload["horizon_1"]["arms"]["age only"]["average_precision"]
    print(f"horizon 1: age {age:.4f} -> age + evidence {both:.4f} (+{both - age:.4f})")
    print(
        f"forward {QUOTED_SPLIT}: top 50 holds {quoted['both_hits_at_50']} "
        f"against age's {quoted['age_hits_at_50']}"
    )
    print(
        f"anchor cohort: {cohort['hits_in_top_k']} of {len(cohort['ranks'])} in the top "
        f"{cohort['top_k']}, chance gives {cohort['expected_in_top_k']:.1f}"
    )
    print(f"\nwrote {SITE_DATA.relative_to(ROOT)} ({SITE_DATA.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
