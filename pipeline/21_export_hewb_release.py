"""Assemble the public HEWB v1.4 release package.

Move 2 of ``STRATEGY_SCOPE.md`` (ship): turn the private benchmark result into a
citable, reproducible public artifact — the frozen manifest, the result tables,
and the robustness evidence — laid out as a HuggingFace-ready dataset directory
under ``release/hewb-v{version}/``.

This is a packaging step, not a compute step: it reads the already-generated
``data/processed`` outputs of ``pipeline/12_run_hewb.py`` (the benchmark) and
``pipeline/20_run_robustness.py`` (the capstone), plus the frozen benchmark
definition from ``benchmark/hewb.py``, and writes a clean, self-describing
release. It never re-scores anything, so the published numbers are exactly the
ones the pipeline produced and the DEV_LOG recorded — no second code path that
could disagree.

The release directory is committed (not gitignored like ``data/``): it *is* the
public deliverable. The prose dataset card (``README.md``) is written by hand,
not generated here — honest framing is not a template.

Usage:
    python pipeline/21_export_hewb_release.py
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from hazium.benchmark.hewb import (
    ANNUAL_CUTOFFS,
    HEWB_VERSION,
    K_VALUES,
    LANDMARK_CASES,
)

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"
RELEASE = ROOT / "release" / f"hewb-v{HEWB_VERSION}"
DATA_OUT = RELEASE / "data"

LABEL_VARIANTS = {
    "headline": "EU non-renewal only (a completed regulatory withdrawal)",
    "early_warning": (
        "EU non-renewal + a started Swedish national reevaluation "
        "(an earlier, weaker signal; the only variant under which fluazinam is a positive)"
    ),
}

#: The processed tables copied verbatim into the release, and the public name
#: each takes. Source of record for every number in the dataset card.
TABLE_MAP = {
    "hewb_aggregate.csv": "aggregate.csv",
    "hewb_lead_times.csv": "lead_times.csv",
    "hewb_rank_trajectories.csv": "rank_trajectories.csv",
    "robustness_placebo.csv": "robustness_label_shuffle_placebo.csv",
    "robustness_cutoff_sweep_aggregate.csv": "robustness_cutoff_sweep_aggregate.csv",
    "robustness_cutoff_sweep_ranks.csv": "robustness_cutoff_sweep_ranks.csv",
    "robustness_negative_controls.csv": "robustness_negative_controls.csv",
    "robustness_shap_funnel.csv": "robustness_shap_funnel.csv",
}


def _action_dates_by_landmark() -> dict[str, dict[str, str]]:
    """Each landmark's label-defining action date per variant, read back from
    the lead-times table (constant across k rows). ``{}`` for a landmark with no
    action under a variant (e.g. fluazinam under headline)."""
    path = PROCESSED / "hewb_lead_times.csv"
    out: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split(",")
        i_variant, i_case, i_action = (
            header.index("variant"),
            header.index("case"),
            header.index("action_date"),
        )
        for line in f:
            cells = line.rstrip("\n").split(",")
            out.setdefault(cells[i_case], {})[cells[i_variant]] = cells[i_action]
    return out


def _write_manifest() -> None:
    action_dates = _action_dates_by_landmark()
    landmarks = [
        {
            "name": c.name,
            "cas": c.cas,
            "note": c.note,
            "action_dates": action_dates.get(c.name, {}),
        }
        for c in LANDMARK_CASES
    ]
    manifest = {
        "benchmark": "HEWB",
        "full_name": "Hazium Early Warning Benchmark",
        "version": HEWB_VERSION,
        "summary": (
            "A retrodetection benchmark: under strict as-of temporal discipline, "
            "how many months before each real EU pesticide regulatory action would "
            "an evidence-only model have flagged the substance."
        ),
        "temporal_discipline": (
            "Every fact carries a known_at date; the model at cutoff T sees only "
            "facts dated strictly before T. Lead time is measured from the earliest "
            "cutoff that flags a substance within top-k to its real EU action date."
        ),
        "cutoffs": [d.isoformat() for d in ANNUAL_CUTOFFS],
        "k_values": list(K_VALUES),
        "label_variants": LABEL_VARIANTS,
        "landmarks": landmarks,
        "metrics": [
            "average_precision (vs trivial baselines, per cutoff)",
            "precision_at_k / recall_at_k / lift_at_k",
            "lead_time_months (per landmark, per k)",
        ],
        "robustness": {
            "label_shuffle_placebo": "permutation test; the project kill-criterion",
            "cutoff_sweep": "aggregate AP + north-star rank across 2020-2024",
            "negative_controls": "reviewed-but-not-banned specificity test",
            "shap_funnel_split": "inside-funnel vs outside-funnel feature attribution",
        },
        "reproduce": (
            "python pipeline/12_run_hewb.py && "
            "python pipeline/20_run_robustness.py && "
            "python pipeline/21_export_hewb_release.py"
        ),
        "generated_by": "pipeline/21_export_hewb_release.py",
    }
    (RELEASE / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _copy_tables() -> list[str]:
    DATA_OUT.mkdir(parents=True, exist_ok=True)
    copied = []
    for src_name, dst_name in TABLE_MAP.items():
        src = PROCESSED / src_name
        if not src.exists():
            raise FileNotFoundError(
                f"missing {src} — run pipeline/12 (HEWB) and pipeline/20 (robustness) first"
            )
        shutil.copyfile(src, DATA_OUT / dst_name)
        copied.append(dst_name)
    return copied


def main() -> int:
    RELEASE.mkdir(parents=True, exist_ok=True)
    _write_manifest()
    copied = _copy_tables()
    print(f"HEWB v{HEWB_VERSION} release assembled at {RELEASE}")
    print(f"  manifest.json + {len(copied)} tables in data/")
    for name in copied:
        print(f"    data/{name}")
    print("\n  README.md (dataset card) is hand-written, not generated here.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
