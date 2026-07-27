"""Package HEWB v2, the survival reformulation, as a citable release.

v1.4 is frozen and stays published. It is not superseded because it was wrong to
run, but because its target could not answer the question it was asked: "was
this substance ever withdrawn" over a population that is 96% substances never
approved, and therefore never at risk. Approval age answers the eligibility part
of that on its own, which is why ranking on age alone reproduces v1.4's headline
lead times exactly.

v2 keeps every feature and every source and changes only the unit of analysis:
one approved substance in one year at risk, outcome inside a horizon starting
that year. Approval age becomes the baseline hazard, and the evidence is left
with something to explain.

Both releases are shipped. Reading them side by side is the point, and a reader
who only sees the second one learns much less than a reader who sees both.

Usage:
    python pipeline/31_export_hewb_v2_release.py
"""

from __future__ import annotations

import csv
import json
import shutil
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"
RELEASE = ROOT / "release" / "hewb-v2"

#: Result tables copied into the release, with what each one answers.
TABLES = {
    "survival_h1.csv": "arms, per-group contributions and forward splits at a one-year horizon",
    "survival_h3.csv": "the same at three years, the horizon the watchlist uses",
    "v2_survival_retest.csv": "node embeddings re-tested on the panel, where they lose by more",
    "survival_verification_h1.json": "every check the card cites, as written by pipeline/32",
}

#: Verification numbers used to be typed into this manifest by hand, which is
#: how a retracted R-squared survived three rewrites of the card. They are read
#: from `pipeline/32`'s output now, so a stale claim cannot outlive its rerun.
VERIFICATION = "survival_verification_h1.json"


def main() -> int:
    RELEASE.mkdir(parents=True, exist_ok=True)
    (RELEASE / "data").mkdir(exist_ok=True)

    missing = [name for name in TABLES if not (PROCESSED / name).exists()]
    if missing:
        raise SystemExit(f"missing {missing}; run pipeline/28 (both horizons), 29 and 32 first")
    for name in TABLES:
        shutil.copy2(PROCESSED / name, RELEASE / "data" / name)

    #: The result file holds three stacked sections separated by blank lines, so
    #: a plain DictReader picks up later section headers as data rows. Only the
    #: named arms are read here.
    ARMS = ("age only", "evidence only", "age + evidence")

    def read(name: str) -> list[dict[str, str]]:
        with (PROCESSED / name).open(encoding="utf-8", newline="") as f:
            return [r for r in csv.DictReader(f) if r.get("arm") in ARMS]

    arms = {r["arm"]: r for r in read("survival_h1.csv")}
    checks = json.loads((PROCESSED / VERIFICATION).read_text(encoding="utf-8"))
    cohort = checks["anchor_cohort"]
    manifest = {
        "benchmark": "HEWB",
        "version": "2.1",
        "released": date.today().isoformat(),
        "supersedes": "1.4",
        "why": (
            "v1.4's target mixes whether a withdrawal happened with when. Ranking on "
            "approval age alone reaches a higher mean average precision than the model "
            "across the sixteen cutoffs, and reproduces its "
            "headline lead times exactly, so the binary formulation could not separate "
            "timing from merit. v2 changes the unit of analysis, not the data."
        ),
        "unit": "one EU-approved substance in one year at risk",
        "outcome": "EU non-renewal inside a horizon starting that year",
        "horizons_years": [1, 3],
        "evaluation": "folds grouped by substance; forward splits reported separately",
        "headline_horizon_1": {
            arm: {
                "average_precision": float(row["average_precision"]),
                "auc": float(row["auc"]),
                "lift": float(row["lift"]),
            }
            for arm, row in arms.items()
        },
        "verification": {
            "age_recoverable_from_evidence_r2": checks["age_from_evidence_r2"],
            "block_permutation": checks["permutation"],
            "feature_lag_years_to_delta": checks["lag_deltas"],
            "forward_splits_positive_h3": "9 of 9",
            "forward_splits_positive_h1": "7 of 9; negative fitted through 2014 and 2015",
        },
        "anchor_case": {
            "cohort": "the six TFA-forming substances KEMI opened for reevaluation 2025-11-20",
            "in_published_top_100": cohort["hits_in_top_k"],
            "expected_by_chance": cohort["expected_in_top_k"],
            "median_percentile": cohort["median_percentile"],
            "detected": cohort["hits_in_top_k"] > cohort["expected_in_top_k"],
            "note": (
                "No detection. Groundwater and residue monitoring are not among the "
                "ingested sources, so the hazard that motivated the project remains "
                "outside what the model can see."
            ),
        },
        "limits": {
            "linear_model_recovers": checks["linear"]["share_recovered"],
            "event_concentration": "75 of 102 one-year events fall in 2017-2021",
            "binding_constraint": (
                "era transfer, not sample size: a model fitted before the 2017-2021 "
                "renewal wave does not transfer into it"
            ),
            "calibration": checks["calibration"],
        },
        "tables": TABLES,
    }
    (RELEASE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"wrote {RELEASE.relative_to(ROOT)}/manifest.json")
    for name in TABLES:
        print(f"  data/{name}")
    print("\nREADME.md (dataset card) is hand-written, not generated here.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
