---
license: cc-by-4.0
language:
  - en
pretty_name: "HEWB v2: survival reformulation"
tags:
  - chemistry
  - regulatory
  - pesticides
  - early-warning
  - temporal
  - benchmark
  - survival-analysis
size_categories:
  - n<1K
---

# HEWB v2: the survival reformulation

v2 changes one thing about v1.4: the unit of analysis. Every feature, every
source and every temporal rule is carried over unchanged.

It exists because v1.4 could not answer the question it was asked, and finding
that out is the most useful thing this benchmark has produced.

## What was wrong with v1.4

v1.4 asks whether a substance was ever withdrawn, over a population of about
5,900 substances of which roughly 96% were never approved in the EU and
therefore could never be withdrawn at all. Answering that is mostly an
eligibility test, and approval age performs it.

Measured directly: ranking on approval age alone, a single date subtraction with
no model, reaches **98% of the full model's mean average precision** across the
sixteen cutoffs, wins outright at **11 of 16**, and reproduces the headline lead
times exactly. Chlorpyrifos at 132 months, thiacloprid at 133, clothianidin at
120, propikonazol at 119. On chlorpyrifos-methyl and mancozeb it does better.

That is not leakage. Approval date is knowable at every cutoff. It is a target
that mixes *whether* a withdrawal happened with *when*, and time wins.

v1.4 remains published and is not retracted. Its results are correct for the
question it asked. Read the two together.

## What v2 does instead

One row per EU-approved substance per year at risk. The outcome is whether the
withdrawal landed inside a horizon starting that year. Approval age becomes the
baseline hazard, which is what it is, and the evidence is left to explain the
rest.

The baseline hazard is steep, and worth seeing before any model:

| approval age | rows | events | annual hazard |
|---|---|---|---|
| 0-5 years | 1,150 | 3 | 0.26% |
| 5-10 | 1,390 | 13 | 0.94% |
| 10-15 | 838 | 66 | 7.88% |
| 15-20 | 177 | 18 | 10.17% |
| 20+ | 9 | 2 | 22.22% |

## Result

One-year horizon, 3,564 substance-years over 352 substances, 102 events, base
rate 2.86%, folds grouped by substance so no substance straddles a split:

| arm | average precision | lift | AUC |
|---|---|---|---|
| approval age alone | 0.102 | 3.6x | 0.836 |
| evidence alone | 0.180 | 6.3x | 0.753 |
| **age + evidence** | **0.242** | **8.4x** | **0.880** |

The gain over age alone is **+0.140** against a seed spread of ±0.029.

Per source, added to age on its own: EFSA +0.081, graph structure +0.034, sales
+0.006, literature +0.001, CLP −0.001, CLH intentions −0.005. Two groups are
slightly negative and are kept anyway, because dropping a feature group after
seeing its sign is how a benchmark stops measuring anything.

EFSA and CLH read the regulator's own pipeline. Measured as blocks, in-funnel
contributes **+0.085** and out-of-funnel **+0.067**, so the result does not rest
on reading regulatory intent.

## Verification

Reproduce every number below with `python pipeline/32_verify_survival.py`. It
writes `data/survival_verification_h1.json`, which this card and the manifest
are generated against.

**Approval age is about 47% recoverable from the evidence** (R² = 0.473, random
forest, folds grouped by substance). The "evidence only" arm is therefore *not*
an age-free arm and must not be read as one. This corrects an earlier claim in
this card that the two were independent at R² = −0.009; see Corrections.

The headline comparison does not depend on it. Both the baseline and the full
model are given the approval-age features explicitly, so the +0.140 is measured
over and above age whether or not the evidence also encodes age.

**The signal survives lagging every feature.** Predicting year T from evidence
1, 2 and 3 years old gives +0.058, +0.053 and +0.026 against +0.124 at lag zero.
It decays rather than collapsing, so it is not an artefact of activity
immediately before a decision.

**Block permutation: p = 0.024** across 40 shuffles, permuting whole substance
histories so the panel structure survives. Real 0.222 against a best shuffled
0.073.

**Forward splits, fit on year Y and scored on everything after.** At three
years, positive in **9 of 9**, mean +0.098. At one year, positive in **7 of 9**;
the two fitted through 2014 and 2015 are negative, which is an era-transfer
problem rather than a sample-size one (see Limits).

**Decision utility.** One-year horizon, fit on 2019 and earlier, scored on 2020
onward: the top 50 contains **11 real withdrawals against approval age's 4**.

## The anchor case, which it fails

Hazium was built because of fluazinam. The honest report is that v2 does not
find it, and this is measured rather than asserted.

Kemikalieinspektionen opened a reevaluation of six TFA-forming plant protection
substances on 2025-11-20. That cohort is dated, externally defined and chosen by
a regulator rather than by this project, which is what makes it a test instead of
an anecdote. Their positions in the v2 three-year ranking of 260 approved
substances:

| substance | rank of 260 |
|---|---|
| Fluazinam | 117 |
| Flonicamid | 128 |
| Diflufenican | 146 |
| Fluopyram | 190 |
| Mefentrifluconazole | 213 |
| tau-fluvalinate | 225 |

**None reaches the published top 100, where chance alone would put 2.3 of them.**
The cohort median sits at the 65th percentile, worse than a random draw. This is
not a detection.

The reason is not a modelling failure. Groundwater and residue monitoring are not
among the ingested sources, and TFA is a degradation product that the parent
substance's own regulatory record never mentions. The signal is absent from the
inputs, so no reformulation of the target can recover it.

Reading a single member of that cohort would have told the opposite story. At an
earlier stage of this work fluazinam sat at 96 and inside the published band,
which reads as a hit until the other five are put beside it. `benchmark/anchor.py`
exists so that the cohort, and not the convenient member, is what gets reported.

## Limits

- A **linear model recovers about a fifth** of the boosted-tree gain (20%), so
  the effect lives in interactions rather than in any single feature.
- **75 of the 102 one-year events fall in 2017-2021**, the EU renewal wave, and
  this is the binding limit. Forward splits fit on 2014 or 2015 give a *negative*
  delta. That was first reported as a sample-size floor of about sixteen events;
  a subsampling test showed that reading to be wrong. Holding the test set fixed
  and varying only how many training events are kept, the delta stays positive
  down to four events. What fails is transfer between regulatory eras.
- **Raw scores are badly calibrated** and must not be read as probabilities. The
  top out-of-fold bin predicts 0.548 against an observed 0.131. Isotonic
  regression on out-of-fold predictions more than halves the Brier score, from
  0.059 to 0.024, and leaves the ranking intact.
- Node embeddings were re-tested on this panel, where coverage roughly doubles
  from the 29.2% that closed the V2 gate to **65.3%**, refit per year against
  that year's `as_of` view. They lose by more here: adding them moves average
  precision from 0.242 to **0.176**, and alone they reach AUC 0.548, close to
  random. The V2 gate stays closed, now for a reason that survives the coverage
  objection.
- The outcome is EU non-renewal, a committee decision. It correlates with harm
  loosely and is not a measure of it. The anchor case above is the clearest
  illustration: a real groundwater hazard, and no rank to show for it.

## Corrections

This card has been wrong twice. Both are left visible rather than edited away.

**Approval-age recoverability (2026-07-26).** Reported as R² = −0.009, evidence
of two independent arms. The check used an unshuffled `KFold` on a panel built
year by year and concatenated, so it split on time: it trained on early years and
tested on late ones, where mean approval age has drifted from 3.5 to 10.4 years
and the target lies outside the training range. A near-zero R² was guaranteed by
the split design rather than by the data. Grouped by substance the answer is
+0.473. `pipeline/32` prints both, so the mistake cannot be repeated silently.

**Empty feature group (2026-07-26).** The panel builder never passed ECHA
CLH-intention records through to the feature builder, so that whole group sat at
zero while this card described its contribution. Wiring it in moved the headline
from 0.253 to 0.242 and the forward-split top 50 from 15 hits to 11. The lower
numbers are the published ones.

## Files

| file | what it answers |
|---|---|
| `data/survival_h1.csv` | arms, per-group and per-block contributions, forward splits, one-year horizon |
| `data/survival_h3.csv` | the same at three years, the horizon the watchlist uses |
| `data/v2_survival_retest.csv` | node embeddings re-tested on the panel |
| `data/survival_verification_h1.json` | every check in Verification, as written by `pipeline/32` |
| `manifest.json` | machine-readable summary, generated from the above |

## Reproduce

```bash
python pipeline/28_run_survival.py --horizon 1
python pipeline/28_run_survival.py --horizon 3
python pipeline/29_retest_v2_survival.py
python pipeline/30_survival_watchlist.py --horizon 3
python pipeline/32_verify_survival.py --horizon 1
python pipeline/31_export_hewb_v2_release.py
```

## Citation

Blomqvist, M. (2026). *HEWB v2: the Hazium Early Warning Benchmark, survival
reformulation.* https://github.com/MartinBlomqvistDev/hazium
