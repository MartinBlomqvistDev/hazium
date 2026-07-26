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

One-year horizon, 3,564 substance-years, 102 events, base rate 2.86%, folds
grouped by substance so no substance straddles a split:

| arm | average precision | lift | AUC |
|---|---|---|---|
| approval age alone | 0.102 | 3.6x | 0.836 |
| evidence alone | 0.179 | 6.3x | 0.751 |
| **age + evidence** | **0.253** | **8.9x** | **0.877** |

The gain over age alone is **+0.151** against a seed spread of ±0.032.

Per source, added to age on its own: EFSA +0.081, graph structure +0.034, CLP
+0.001, sales +0.006, literature +0.001, CLH intentions +0.000. EFSA and CLH read
the regulator's own pipeline; measured as blocks, in-funnel contributes +0.072
and out-of-funnel +0.062, so the result does not rest on reading regulatory
intent.

## Verification

Five checks, each capable of killing the result.

**Approval age is not recoverable from the evidence** (R² = −0.009, worse than
predicting the mean). The two are genuinely separate rather than one restating
the other, so "evidence-only" is not age in disguise.

**The signal survives lagging every feature.** Predicting year T from evidence
1, 2 and 3 years old gives +0.056, +0.045 and +0.029 against +0.141 at lag zero.
It decays rather than collapsing, so it is not an artefact of activity
immediately before a decision.

**Block permutation over substances: p = 0.024** across 40 shuffles, permuting
whole substance histories so the panel structure survives.

**Forward splits, fit on year Y and scored on everything after.** At the
three-year horizon, positive in **9 of 9** splits, mean +0.092. At one year, 6 of
6 from 2017 onward. The two earliest one-year splits, fit on 2014 and 2015, are
negative; see Limits for why that is an era-transfer problem rather than a
sample-size one.

**Decision utility.** Fit on 2019 and earlier, scored on 2020 onward: the top 50
contains **15 real withdrawals against approval age's 4**.

## Limits

- A **linear model recovers about a fifth** of the boosted-tree gain, so the
  effect lives in interactions rather than in any single feature.
- **75 of the 102 one-year events fall in 2017-2021**, the EU renewal wave, and
  this is the binding limit. Forward splits fit on 2014 or 2015 give a *negative*
  delta. That was first reported here as a sample-size floor of about sixteen
  events; a subsampling test has since shown that reading to be wrong. Holding
  the test set fixed and varying only how many training events are kept, the
  delta stays positive down to four events. What fails is transfer between
  regulatory eras, not learning from few examples.
- **Raw scores are badly calibrated** and must not be read as probabilities. The
  top out-of-fold bin predicts 0.566 against an observed 0.128. Isotonic
  regression on out-of-fold predictions more than halves the Brier score, from
  0.061 to 0.024, and leaves the ranking intact.
- Node embeddings were re-tested on this panel, where coverage roughly doubles
  from the 29.2% that closed the V2 gate to **65.3%**, refit per year against
  that year's `as_of` view. They lose by more here: adding them moves average
  precision from 0.253 to **0.173**, and alone they reach AUC 0.548, close to
  random. The V2 gate stays closed, now for a reason that survives the coverage
  objection.

## Files

| file | what it answers |
|---|---|
| `data/survival_h1.csv` | arms, per-group contributions and forward splits, one-year horizon |
| `data/survival_h3.csv` | the same at three years, the horizon the watchlist uses |
| `data/v2_survival_retest.csv` | node embeddings re-tested on the panel |
| `manifest.json` | machine-readable summary of the above |

## Reproduce

```bash
python pipeline/28_run_survival.py --horizon 1
python pipeline/28_run_survival.py --horizon 3
python pipeline/29_retest_v2_survival.py
python pipeline/31_export_hewb_v2_release.py
```

## Citation

Blomqvist, M. (2026). *HEWB v2: the Hazium Early Warning Benchmark, survival
reformulation.* https://github.com/MartinBlomqvistDev/hazium
