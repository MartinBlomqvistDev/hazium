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

Both are always reported. The broadened variant is not a replacement for the
headline; its extra positives currently trace to a single Swedish reevaluation
announcement, which is a real but narrow evidence source, and it is labelled as
such.

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
against a best trivial baseline of **0.016**, a roughly 16x lead over the
strongest dead-simple ranker on the identical population and split. It beats
every trivial baseline at every cutoff. Full per-cutoff numbers are in
`data/aggregate.csv`; per-landmark trajectories in `data/rank_trajectories.csv`.

A note on counting, because two honest numbers appear in this project. HEWB
measures "flagged within top-50 before the action" (9 of 10). The public site
uses a stricter frame, "flagged ahead of the EU's own first action" (7 of 10),
which measures against the EU's first move rather than the final ban. Both are
reported, and they are not in tension: they answer slightly different questions.

## Robustness (v1.4 capstone)

Four tests, so the headline survives a skeptical reader. All raw outputs are in
`data/robustness_*.csv`.

1. **Label-shuffle placebo (the kill-criterion).** Permute the labels, keep the
   class balance, refit. Real average precision must tower over the shuffled
   null or the result is an artifact and must be retracted. It does: real 0.230
   (headline) and 0.191 (early-warning) against a shuffled null whose maximum
   over 50 permutations is 0.013 and 0.016. Permutation p = 0.020, the floor for
   50 permutations. The signal is real.

2. **Cutoff sensitivity.** The learned model beats the best trivial baseline at
   every cutoff 2020-2024 (6.8x to 15.8x under the headline label), so the
   result is not a single-cutoff accident. The anchor case, fluazinam, ranks
   between 111th and 250th of about 5,900 substances (top 2 to 4 percent) at
   every cutoff under the `early_warning` label. The 2023 number is
   representative, not selected.

3. **Negative controls (specificity).** Substances that went through EU review
   and stayed approved should not crowd the top of the ranking. The true
   positives sit at a median 1.0 percentile; approved-and-surviving substances
   sit deeper at 2.6 percentile; and substances that carry a severe hazard
   classification yet were never actioned put zero substances in the top 10. The
   model is not simply flagging whatever looks hazardous.

4. **Feature attribution, inside vs outside the funnel.** Signals split into
   inside-funnel (reading the regulator's own pipeline: EFSA activity, ECHA
   intentions) and outside-funnel (independent scientific literature). The
   attribution is honest about what carries the model: an approval-age prior
   dominates at about 52 percent of total attribution, and among the substantive
   evidence signals the outside-funnel literature feature (the second most
   important single feature overall) is on par with the inside-funnel
   regulatory-concern signals, 14 percent against 16 percent. The independent
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

The feed-additive case is the most instructive. It is the only one of the four with a
large positive class, and a model trained on it would likely have scored well while
measuring the wrong thing: "which legacy additive did nobody reapply for" is
learnable almost entirely from approval age, which is already the single largest
feature in this model. A large label set measuring the wrong construct is more
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
