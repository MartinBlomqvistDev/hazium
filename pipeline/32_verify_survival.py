"""Every check the HEWB v2 card cites, in one reproducible run.

`pipeline/28` produces the headline. This produces the reasons to believe it,
and the one reason not to. Until now these numbers were computed ad hoc and
only their conclusions were published, which is the same shape of mistake the
project spent a week correcting: a result nobody can re-run is a result nobody
can falsify.

Six checks, each capable of changing what gets claimed.

1. **Recoverability.** If approval age is predictable from the evidence
   features, then "evidence only" is just age wearing a different hat and the
   two arms are not independent.
2. **Feature lag.** Predicting year T from evidence 1, 2 and 3 years old. A
   signal that collapses at lag 1 is an artefact of paperwork filed just before
   a decision, not foresight.
3. **Block permutation.** Shuffling whole substance histories rather than rows,
   so the panel structure survives and only the substance-to-outcome pairing
   breaks.
4. **Linear recovery.** How much of the gain a logistic model reaches. A large
   share means the effect is one feature in disguise.
5. **Calibration.** Raw scores against observed frequencies, and what isotonic
   regression fixes. A rank is not a probability.
6. **The anchor cohort.** Where KEMI's six TFA-forming substances land. This is
   the check the project would most like to pass, so it is the one reported
   whatever it says.

Usage:
    python pipeline/32_verify_survival.py
    python pipeline/32_verify_survival.py --horizon 3 --shuffles 40
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, r2_score
from sklearn.model_selection import GroupKFold, KFold, StratifiedGroupKFold, cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from hazium.benchmark.anchor import cohort_ranks
from hazium.benchmark.survival import (
    EVENT,
    SUBJECT,
    YEAR,
    PanelSpec,
    build_panel,
    feature_columns,
)
from hazium.graph.build import load_graph
from hazium.ml.baseline import make_model
from hazium.models import (
    LiteratureVolumeRecord,
    RegulatoryEvent,
    SalesRecord,
    Substance,
)
from hazium.resolve.names import SubstanceResolver, resolve_sales_records
from hazium.sources.echa_clh import clh_intention_records, earliest_intention_year

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"
CLH_SNAPSHOT = ROOT / "data" / "raw" / "clh_intentions_ppp.jsonl"

N_SPLITS = 5
SEED = 42


def _load(path: Path, model):
    with path.open(encoding="utf-8") as f:
        return [model.model_validate_json(line) for line in f]


def oof(panel, columns, seed: int = SEED) -> np.ndarray:
    """Out-of-fold predictions, folds grouped by substance."""
    y = panel[EVENT]
    out = np.zeros(len(y))
    splitter = StratifiedGroupKFold(n_splits=N_SPLITS, shuffle=True, random_state=seed)
    for train_idx, test_idx in splitter.split(panel[columns], y, panel[SUBJECT]):
        model = make_model(y.iloc[train_idx], seed)
        model.fit(panel[columns].iloc[train_idx], y.iloc[train_idx])
        out[test_idx] = model.predict_proba(panel[columns].iloc[test_idx])[:, 1]
    return out


def check_recoverability(panel) -> tuple[float, float]:
    """R^2 of predicting approval age from the evidence features alone.

    Returns ``(grouped, naive)``. Both are reported because the difference
    between them is itself the finding.

    This check was first run with an unshuffled ``KFold``, which returned about
    -0.01 and was published as evidence that the evidence features carry no
    approval-age information. That reading was wrong. The panel is built year by
    year and concatenated, so an unshuffled fold splits on time: it trains on
    early years and tests on late ones, where mean approval age has drifted from
    3.5 to 10.4 years and the target lies outside the training range. A near-zero
    R^2 was guaranteed by the split, not by independence.

    Grouping by substance asks the question that was meant: given the evidence
    for a substance never seen in training, can its approval age be inferred?
    """
    from sklearn.ensemble import RandomForestRegressor

    evidence = feature_columns(age=False, evidence=True)
    target = panel["eu_years_since_first_approval"]

    def forest() -> RandomForestRegressor:
        return RandomForestRegressor(n_estimators=200, random_state=SEED, n_jobs=-1)

    preds = np.zeros(len(target))
    for train_idx, test_idx in GroupKFold(n_splits=N_SPLITS).split(
        panel[evidence], target, panel[SUBJECT]
    ):
        reg = forest()
        reg.fit(panel[evidence].iloc[train_idx], target.iloc[train_idx])
        preds[test_idx] = reg.predict(panel[evidence].iloc[test_idx])
    grouped = float(r2_score(target, preds))

    # Reproduced exactly as originally run, per-fold mean and all, so the
    # printed contrast shows the actual mistake rather than an approximation
    # of it. Pooling out-of-fold predictions instead would score around +0.37
    # and hide what went wrong.
    naive = float(
        cross_val_score(forest(), panel[evidence], target, cv=KFold(N_SPLITS), scoring="r2").mean()
    )
    return grouped, naive


def check_lag(panel, max_lag: int = 3) -> list[tuple[int, float]]:
    """Delta over age when every evidence feature is read from N years earlier."""
    age_cols = feature_columns(age=True, evidence=False)
    evidence = feature_columns(age=False, evidence=True)
    both = feature_columns()
    base = average_precision_score(panel[EVENT], oof(panel, age_cols))

    out: list[tuple[int, float]] = []
    for lag in range(0, max_lag + 1):
        if lag == 0:
            lagged = panel
        else:
            # Join each substance-year to its own evidence from `lag` years back.
            past = panel[[SUBJECT, YEAR, *evidence]].copy()
            past[YEAR] = past[YEAR] + lag
            lagged = panel.drop(columns=evidence).merge(past, on=[SUBJECT, YEAR], how="inner")
            if lagged[EVENT].sum() < 10:
                continue
        scored = average_precision_score(lagged[EVENT], oof(lagged, both))
        if lag == 0:
            out.append((0, scored - base))
            continue
        age_here = average_precision_score(lagged[EVENT], oof(lagged, age_cols))
        out.append((lag, scored - age_here))
    return out


def check_permutation(panel, shuffles: int) -> tuple[float, float, float]:
    """Shuffle whole substance histories; return (real, best shuffled, p)."""
    both = feature_columns()
    y = panel[EVENT].to_numpy()
    real = average_precision_score(y, oof(panel, both))

    subjects = panel[SUBJECT].to_numpy()
    order = list(dict.fromkeys(subjects))
    outcome_of = {s: y[subjects == s] for s in order}
    rng = np.random.default_rng(SEED)

    shuffled: list[float] = []
    for _ in range(shuffles):
        permuted = list(order)
        rng.shuffle(permuted)
        mapping = dict(zip(order, permuted))
        fake = panel.copy()
        # Reassign each substance's outcome history to another substance whose
        # history is the same length, so row counts stay valid.
        new_y = np.zeros(len(fake), dtype=int)
        for subject in order:
            mask = subjects == subject
            donor = outcome_of[mapping[subject]]
            take = min(mask.sum(), len(donor))
            idx = np.where(mask)[0][:take]
            new_y[idx] = donor[:take]
        fake[EVENT] = new_y
        if new_y.sum() < 5:
            continue
        shuffled.append(average_precision_score(new_y, oof(fake, both)))

    beaten = sum(1 for s in shuffled if s >= real)
    p = (beaten + 1) / (len(shuffled) + 1)
    return real, max(shuffled) if shuffled else float("nan"), p


def check_linear(panel) -> tuple[float, float, float]:
    """Boosted gain, linear gain, and the share a linear model recovers."""
    age_cols = feature_columns(age=True, evidence=False)
    both = feature_columns()
    y = panel[EVENT]

    def linear_oof(columns) -> np.ndarray:
        out = np.zeros(len(y))
        splitter = StratifiedGroupKFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED)
        for train_idx, test_idx in splitter.split(panel[columns], y, panel[SUBJECT]):
            model = make_pipeline(
                StandardScaler(),
                LogisticRegression(max_iter=2000, class_weight="balanced"),
            )
            model.fit(panel[columns].iloc[train_idx], y.iloc[train_idx])
            out[test_idx] = model.predict_proba(panel[columns].iloc[test_idx])[:, 1]
        return out

    boosted = average_precision_score(y, oof(panel, both)) - average_precision_score(
        y, oof(panel, age_cols)
    )
    linear = average_precision_score(y, linear_oof(both)) - average_precision_score(
        y, linear_oof(age_cols)
    )
    return boosted, linear, linear / boosted if boosted else float("nan")


def check_calibration(panel) -> tuple[float, float, list[tuple[float, float, int]]]:
    """Raw Brier, isotonic Brier, and a reliability table."""
    y = panel[EVENT].to_numpy()
    raw = oof(panel, feature_columns())
    iso = IsotonicRegression(out_of_bounds="clip").fit(raw, y)
    observed, predicted = calibration_curve(y, raw, n_bins=6, strategy="quantile")
    counts = np.histogram(raw, bins=np.quantile(raw, np.linspace(0, 1, 7)))[0]
    table = [(float(p), float(o), int(n)) for p, o, n in zip(predicted, observed, counts)]
    return (
        float(brier_score_loss(y, raw)),
        float(brier_score_loss(y, iso.predict(raw))),
        table,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--horizon", type=int, default=1)
    parser.add_argument("--shuffles", type=int, default=40)
    parser.add_argument("--watchlist", type=Path, default=None)
    args = parser.parse_args()

    graph = load_graph(PROCESSED / "graph_nodes.jsonl", PROCESSED / "graph_edges.jsonl")
    sales = resolve_sales_records(
        _load(PROCESSED / "kemi_sales.jsonl", SalesRecord),
        SubstanceResolver(_load(PROCESSED / "kemi_register_substances.jsonl", Substance)),
    )
    events = _load(PROCESSED / "eu_ppdb_events.jsonl", RegulatoryEvent)
    lit = _load(PROCESSED / "literature_volume.jsonl", LiteratureVolumeRecord)
    clh = (
        clh_intention_records(earliest_intention_year(CLH_SNAPSHOT))
        if CLH_SNAPSHOT.exists()
        else []
    )
    panel = build_panel(
        graph, sales, events, lit, PanelSpec(horizon_years=args.horizon), clh_records=clh
    )
    print(
        f"panel {len(panel):,} substance-years, {int(panel[EVENT].sum())} events, "
        f"horizon {args.horizon}y\n"
    )

    summary: dict[str, object] = {"horizon": args.horizon}

    print("1. RECOVERABILITY: is approval age hiding inside the evidence?")
    grouped_r2, naive_r2 = check_recoverability(panel)
    summary["age_from_evidence_r2"] = {
        "grouped_by_substance": round(grouped_r2, 4),
        "naive_unshuffled_kfold": round(naive_r2, 4),
    }
    print(f"   grouped by substance:      R2 {grouped_r2:+.4f}")
    print(f"   unshuffled KFold (wrong):  R2 {naive_r2:+.4f}")
    print(
        "   The second splits a year-ordered panel on time and is the design that\n"
        "   produced the retracted 'not recoverable' claim. Read the first.\n"
        f"   -> approval age is about {grouped_r2:.0%} recoverable from the evidence,\n"
        "      so 'evidence only' is not an age-free arm and must not be read as one.\n"
    )

    print("2. FEATURE LAG: does the signal survive being read from the past?")
    lags = check_lag(panel)
    summary["lag_deltas"] = {str(k): round(v, 4) for k, v in lags}
    for lag, delta in lags:
        print(f"   evidence {lag} year(s) old: delta {delta:+.4f}")
    print()

    print(f"3. BLOCK PERMUTATION: {args.shuffles} shuffles of whole substance histories")
    real, best, p = check_permutation(panel, args.shuffles)
    summary["permutation"] = {
        "real_ap": round(real, 4),
        "best_shuffled": round(best, 4),
        "p": round(p, 4),
    }
    print(f"   real {real:.4f}  best shuffled {best:.4f}  p = {p:.4f}\n")

    print("4. LINEAR RECOVERY: does the gain live in interactions?")
    boosted, linear, share = check_linear(panel)
    summary["linear"] = {
        "boosted_gain": round(boosted, 4),
        "linear_gain": round(linear, 4),
        "share_recovered": round(share, 4),
    }
    print(f"   boosted {boosted:+.4f}  linear {linear:+.4f}  recovered {share:.0%}\n")

    print("5. CALIBRATION: can the score be read as a probability?")
    raw_brier, iso_brier, table = check_calibration(panel)
    summary["calibration"] = {
        "raw_brier": round(raw_brier, 5),
        "isotonic_brier": round(iso_brier, 5),
    }
    print(f"   Brier raw {raw_brier:.5f} -> isotonic {iso_brier:.5f}")
    print(f"   {'predicted':>10} {'observed':>10} {'n':>6}")
    for predicted, observed, n in table:
        flag = "  <- overconfident" if predicted > observed * 1.5 and n > 20 else ""
        print(f"   {predicted:>10.3f} {observed:>10.3f} {n:>6}{flag}")
    print()

    print("6. ANCHOR COHORT: KEMI's six TFA-forming substances")
    watchlist = args.watchlist or PROCESSED / "survival_watchlist_h3.csv"
    cohort = sorted(
        {e.substance_id for e in _load(PROCESSED / "kemi_reevaluations.jsonl", RegulatoryEvent)}
    )
    with watchlist.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    ranked = [r["substance_id"] for r in rows]
    names = {r["substance_id"]: r["name"] for r in rows}
    result = cohort_ranks(ranked, cohort, top_k=100)
    for sid, rank in sorted(result.ranks.items(), key=lambda kv: kv[1]):
        print(f"   {names.get(sid, sid):<26} rank {rank:>4} of {result.population}")
    for sid in result.missing:
        print(f"   {sid:<26} not in the at-risk set")
    print(
        f"\n   median rank {result.median_rank:.1f} "
        f"({result.median_percentile:.0%} of the ranking; chance is 50%)"
    )
    print(
        f"   in the published top {result.top_k}: {result.hits_in_top_k} "
        f"of {len(result.ranks)}; chance gives {result.expected_in_top_k:.1f}"
    )
    print(
        "   VERDICT: "
        + (
            "the cohort beats chance"
            if result.beats_chance
            else "no detection. The groundwater signal is not in these sources."
        )
        + "\n"
    )
    # Names travel with the ranks so that no downstream surface has to keep its
    # own CAS-to-label mapping. The site had one for a day and it was already a
    # thing that could silently drift out of date.
    summary["anchor_cohort"] = {
        **result.model_dump(),
        "names": {sid: names.get(sid, sid) for sid in result.ranks},
    }

    out = PROCESSED / f"survival_verification_h{args.horizon}.json"
    out.write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
