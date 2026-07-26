---
license: cc-by-4.0
language:
  - en
pretty_name: "HEWB: Hazium Early Warning Benchmark"
tags:
  - chemistry
  - regulatory
  - pesticides
  - early-warning
  - temporal
  - benchmark
  - explainable-ml
size_categories:
  - n<1K
---

# HEWB: the Hazium Early Warning Benchmark (v1.4)

HEWB measures one thing, precisely: using only evidence that was public before a
given date, how many months ahead of a real EU pesticide regulatory action would
a model have flagged the substance?

It is a retrodetection benchmark over a fixed set of individually-verified
historical EU actions, evaluated under strict temporal discipline, with a
lead-time metric rather than a single accuracy score. It exists to make an
early-warning claim falsifiable instead of anecdotal.

This dataset is the frozen v1.4 release: the benchmark definition, the result
tables, and the robustness evidence. It is the measuring stick behind the
[Hazium](https://github.com/MartinBlomqvistDev/hazium) project.

## The question, stated as a rule

A model at cutoff `T` sees only facts dated strictly before `T`. Every fact and
every graph edge carries a `known_at` date, so a cutoff view is a real
reconstruction of what was knowable at the time, not the present dataset with a
filter applied. Lead time for a landmark is the number of months from the
earliest annual cutoff that ranks it inside the top-`k` to the date of its real
EU action. A flag at or after the action is not early, and is not counted.

- **Cutoffs:** annual, 2009-01-01 through 2024-01-01.
- **Thresholds:** `k` in {10, 20, 50}, reported together, never tuned per case.
- **Population:** every substance with at least one dated pre-cutoff fact
  (roughly 2,600 substances at the 2009 cutoff, growing to about 5,900 by 2023),
  with any substance already actioned before the cutoff censored out.

## Two label variants, reported side by side

| Variant | Positive label | Note |
|---|---|---|
| `headline` | EU non-renewal only | A completed regulatory withdrawal. The strict result. |
| `early_warning` | non-renewal + started Swedish national reevaluation | An earlier, weaker signal. The only variant under which the anchor case, fluazinam, is a positive. |

Both are always reported. The broadened variant is not a replacement for the headline. Its extra positives
currently trace to a single Swedish reevaluation announcement, which is a real but
narrow evidence source, and it is labelled as such.

## The landmark set

Eleven verified historical cases. Each CAS is checked against the graph before
every run, so a lead-time is never computed for the wrong substance. Fluazinam is
the anchor: a negative under the headline label (it has no EU non-renewal) and a
positive only under `early_warning`. It is kept precisely because that honesty is
the point of the benchmark.

The full set, with per-variant action dates, is in `manifest.json`.

## Headline result (v1.4)

Under the strict `headline` label, at `k`=50, **9 of 10 landmarks flag before
their real EU action**, with lead times up to **133 months** (about 11 years):

| Landmark | EU action | Lead at k=50 |
|---|---|---|
| Chlorpyrifos | 2020-01 | 132 months |
| Thiacloprid | 2020-02 | 133 months |
| Chlorpyrifos-methyl | 2020-01 | 120 months |
| Clothianidin | 2019-01 | 120 months |
| Dimethoate | 2019-06 | 125 months |
| Mancozeb | 2021-01 | 132 months |
| Thiamethoxam | 2019-04 | 123 months |
| Propikonazol | 2018-12 | 119 months |
| Imidacloprid | 2020-12 | 95 months |
| Epoxiconazole | 2020-04 | not flagged (the one miss) |

At the 2023-01-01 cutoff the learned model reaches average precision **0.254**
on the identical population and split. Read alongside the approval-age
result below, which is the number that matters. Full per-cutoff numbers are in
`data/aggregate.csv`; per-landmark trajectories in `data/rank_trajectories.csv`.

A note on counting, because two honest numbers appear in this project. HEWB
measures "flagged within top-50 before the action" (9 of 10). The public site
uses a stricter frame, "flagged ahead of the EU's own first action" (7 of 10),
which measures against the EU's first move rather than the final ban. Both are
reported, and they are not in tension: they answer slightly different questions.

> **A second version exists, and it repairs this.** The finding below is that
> v1.4's target could not separate *whether* a substance was withdrawn from
> *when*, so approval age answers most of it. **HEWB v2**, under `v2/` in this
> repository, changes only the unit of analysis: one approved substance in one
> year at risk. On that panel the evidence adds +0.140 average precision over
> approval age alone (p = 0.024), and a forward split finds 11 real withdrawals
> in the top 50 against age's 4. v1.4 is not retracted; read them together.

## The approval-age baseline beats the model

The trivial baselines in this release were severe-hazard count, sales tonnage and
assessment count. All three are weak, and the learned model beat them by roughly
an order of magnitude, which is how the headline was long reported. Approval age
was never tested as a baseline, because it sat inside the model as a feature.

Ranking on approval age alone reaches **98% of the model's mean average
precision** across the sixteen cutoffs, wins outright at **11 of 16**, and
reproduces the headline lead times exactly: chlorpyrifos at 132 months,
thiacloprid at 133, clothianidin at 120, propikonazol at 119. On
chlorpyrifos-methyl and mancozeb it beats the model. Dropping the two
approval-age features leaves the model at **37%** of its performance.

| | XGBoost | approval age (1 feature) |
|---|---|---|
| landmarks flagged, k=50 | 9 of 10 | 8 of 10 |
| mean AP across 16 cutoffs | 0.467 | 0.459 |
| cutoffs won | 5 of 16 | 11 of 16 |

The mechanism is structural. A substance can only be non-renewed when its
approval comes up for renewal, and approval age proxies proximity to that
decision, so the ranking substantially answers *whose turn it is* rather than
*who fails*. Approval date is knowable at every cutoff, so this is not leakage,
but it is a different question from the one this benchmark was built to ask.

The six evidence groups are therefore worth, over a date subtraction, one extra
landmark out of ten and 0.008 average precision. `approval_age` is reported as a
trivial baseline from this point on, and by the project's own baseline rule it is
the published result until a learned model beats it.

Note that the label-shuffle placebo below is unaffected and still passes. It asks
whether the signal is real rather than noise, and approval age is a real signal.
It never asked whether the signal was interesting, which is why the existing
robustness suite could not have caught this.

## Robustness (v1.4 capstone)

Four tests, so the headline survives a skeptical reader. All raw outputs are in
`data/robustness_*.csv`.

1. **Label-shuffle placebo (the kill-criterion).** Permute the labels, keep the
   class balance, refit. Real average precision must tower over the shuffled
   null or the result is an artifact and must be retracted. It does: real 0.230
   (headline) and 0.191 (early-warning) against a shuffled null whose maximum
   over 50 permutations is 0.013 and 0.016. Permutation p = 0.020, the floor for
   50 permutations. The signal is real.

2. **Cutoff sensitivity.** The learned model beats the hazard, sales and assessment baselines at every cutoff 2020-2024, so the result is not a single-cutoff accident. It does not beat approval age: see the section above. The anchor case, fluazinam, ranks
   between 111th and 250th of about 5,900 substances (top 2 to 4 percent) at
   every cutoff under the `early_warning` label. The 2023 number is
   representative, not selected.

3. **Negative controls (specificity).** Substances that went through EU review
   and stayed approved should not crowd the top of the ranking. The true positives sit at a median 1.0 percentile, and approved-and-surviving substances
sit deeper at 2.6 percentile. Substances that carry a severe hazard classification yet
were never actioned put zero substances in the top 10. The
   model is not simply flagging whatever looks hazardous.

4. **Feature attribution, inside vs outside the funnel.** Signals split into
   inside-funnel (reading the regulator's own pipeline: EFSA activity, ECHA
   intentions) and outside-funnel (independent scientific literature). The attribution is honest about what carries the model. An approval-age prior dominates
at about 52 percent of total attribution. Among the substantive evidence signals, the
outside-funnel literature feature (the second most important single feature overall) is
on par with the inside-funnel regulatory-concern signals, 14 percent against 16 percent. The independent
   literature signal carries real weight; it does not merely echo the paperwork.

## Where the method fits, and where it does not

The most transferable finding in this project is a mapped boundary. The method
works where three conditions hold together:

- a **bounded population** (a registry of a few thousand substances, not an open
  universe),
- **dated outcome labels** from an approval-review-withdrawal pipeline (a
  regulatory decision, not a hazard definition), and
- **rich, CAS-joinable per-substance evidence**.

EU pesticides satisfy all three, which is why HEWB works. Four other EU regimes were
tested against the same conditions before any modelling code was written for them.
All four fail, and each fails differently.

| Regime | Fails on | Measured |
|---|---|---|
| PFAS | Population shape, circular labels | Effectively unbounded population; SVHC listing is hazard-defined, so predicting hazard from hazard is circular |
| Biocides (BPR) | Independence, positive-class size | 101 of 239 review-programme actives (42%) are also EU pesticide actives, concentrated in the most informative ones; 286 unique CAS in total because many actives are generated in situ; 15 strict non-approval positives on the independent subset, at a 13% base rate |
| Food additives | Positive-class size, task shape | ~4 clean safety withdrawals from 244 re-evaluated additives; review is calendar-driven (Reg. 257/2010), so entry into the funnel carries no signal; EFSA is both the labeller and the main evidence source |
| Feed additives | Label validity | 309 of 1,958 register records are "not authorised", but 189 (61%) are flavourings withdrawn because no holder reapplied, so the label measures commercial abandonment rather than risk |

The feed-additive case is the most instructive. It is the only one of the four with a large positive class, and a model trained on it
would likely have scored well while measuring the wrong thing. "Which legacy additive
did nobody reapply for" is learnable almost entirely from approval age, which is already
the single largest feature in this model. A large label set measuring the wrong construct is more
dangerous than a small one measuring the right construct, because only the first is
persuasive.

What survives the four negatives is a sharper statement of scope than a second domain
would have provided. The method needs a **risk-triggered** regulatory funnel, over a
bounded population, large enough to generate a meaningful number of **safety-driven**
decisions, with per-substance evidence that is independent of the funnel itself. Of
the regimes examined, EU pesticides is the only one satisfying all of it at once.
Naming where a method breaks, and measuring it before committing to the build, is
part of the result.

## Files

```
manifest.json                                  frozen benchmark definition
data/aggregate.csv                             AP and P@k vs baselines, per cutoff and variant
data/lead_times.csv                            per-landmark lead time, per k
data/rank_trajectories.csv                     per-landmark rank at every cutoff
data/robustness_label_shuffle_placebo.csv      the kill-criterion
data/robustness_cutoff_sweep_aggregate.csv     AP across 2020-2024
data/robustness_cutoff_sweep_ranks.csv         landmark ranks across 2020-2024
data/robustness_negative_controls.csv          specificity test
data/robustness_shap_funnel.csv                inside vs outside funnel attribution
```

## Reproduce

The numbers here are copied verbatim from the pipeline outputs; nothing is
re-scored at packaging time. From the [project repository](https://github.com/MartinBlomqvistDev/hazium):

```
python pipeline/12_run_hewb.py            # the benchmark
python pipeline/20_run_robustness.py      # the capstone
python pipeline/21_export_hewb_release.py # assemble this release
```

## Recent cutoffs are censored, not weak

Precision falls steadily across the cutoff schedule: `precision@50` runs
0.58 to 0.78 for cutoffs from 2009 to 2017, then 0.18 to 0.26 for 2021 to 2024.
Read as a time series that looks like a model getting worse. It is not.

A cutoff can only be graded against outcomes that have already happened. The
2009 cutoff has had seventeen years for its predictions to resolve; the 2024
cutoff has had two. A substance flagged in 2024 and withdrawn in 2031 counts
today as a false positive, and will count as a true positive later, without
anything about the model changing.

The relationship is almost perfectly linear. Across the sixteen cutoffs,
`precision@50` correlates with the number of years of future available at
**r = 0.957**, and with the number of positives that have materialised at
r = 0.832. Degradation would not produce that; right-censoring does.

Two consequences for anyone reading these tables:

- **The mature cutoffs carry the honest estimate of the method.** Around 0.7
  precision at k=50, not the 0.22 the most recent row shows.
- **A forward watchlist cannot be graded early.** Scored two years out it will
  look poor whatever its quality, which is why `pipeline/26_track_resolution.py`
  scores only entries whose approval expiry has actually forced a decision, and
  reports no precision at all while nothing has settled.

Precision is also flat across k on the mature cutoffs, holding a plateau from
k=10 to about k=50 (0.68 to 0.78) before declining: 0.57 to 0.62 at k=100, 0.41
to 0.45 at k=200, 0.18 to 0.20 at k=500. So k=50 is not an arbitrary round
number, it sits at the end of the plateau. Top-50 captures 32 to 38 percent of
all positives, which is the recall that precision buys.

## Limitations

- The `early_warning` label's extra positives trace to a single Swedish
  reevaluation announcement. It is a real signal, but a narrow one.
- "Non-renewal" records that a withdrawal happened and when, not why. Commercial
  and administrative withdrawals are real and are not distinguished here from
  safety-driven ones.
- The result is demonstrated on exactly one regulatory pipeline. The
  generalisation claim is scoped accordingly: four candidate regimes (PFAS,
  biocides, food additives, feed additives) were each measured against the three
  conditions and each failed for a different reason, so no second domain is claimed
  and the boundary is reported instead. See "Where the method fits, and where it
  does not".
- KEMI Swedish sales data begins in 2013, so pre-2013 cutoffs rest entirely on
  EU-wide hazard, approval, and graph features, with no national sales signal.
- The population is built from the EU Pesticides Database bulk export. This was
  audited against the register's own API: the export matches the register's public
  search **exactly**, as a set and not merely in count (1,482 substances).
  Scanning the details endpoint by id reaches 100 further records, of which 87 are
  flagged by the register as not for publication and 13 are superseded or split
  entries whose canonical replacements are already in the population (for example
  an older "Ammonium acetate" record replaced by "Ammonium Acetate", and an
  umbrella pheromone entry since split into three). None of the reachable extras
  contributes a dated non-renewal that the population lacks, so the positive class
  is unaffected.

## Citation

```
Blomqvist, M. (2026). HEWB: the Hazium Early Warning Benchmark (v1.4).
https://github.com/MartinBlomqvistDev/hazium
```
