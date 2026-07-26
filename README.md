# Hazium

[![CI](https://github.com/MartinBlomqvistDev/hazium/actions/workflows/ci.yml/badge.svg)](https://github.com/MartinBlomqvistDev/hazium/actions/workflows/ci.yml)

> Tracing systemic exposure.

**[hazium.org](https://hazium.org)** · benchmark: **[HEWB v1.4 on HuggingFace](https://huggingface.co/datasets/MartinBlomqvist/hewb)**

Hazium is an explainable machine learning platform. It builds a temporally-aware knowledge graph of environmental and public-health evidence from heterogeneous public data: regulatory decisions, hazard classifications, national sales statistics, residue monitoring, and scientific conclusions. Machine learning over that graph ranks substances for future regulatory risk, and every signal traces back to the source evidence behind it.

Every model here is reported against the simplest thing that could replace it. One of those baselines, ranking on approval age alone, matched the original headline: a date subtraction. The cause was the question rather than the data, and reframing it as a survival problem recovered a measurable contribution from the evidence. All three steps are below in that order, with two later corrections to the repair and the hazard the finished system does not find.

The first domain is pesticides, with a Nordic focus. The intelligence is in the ML; large language models are used for presentation only.

## The north-star question

> Using only data known before 2023-01-01, does Hazium rank fluazinam, the fungicide at the centre of Sweden's 2026 pesticide controversy, among the highest-concern substances approved in Sweden?

Every version of the system is measured against this retrodetection question under strict temporal discipline. Every fact and every edge carries a `known_at` timestamp, and a model evaluated at a given cutoff never sees evidence dated on or after it.

**The current answer is no.** Asked of all six substances the Swedish regulator named rather than of fluazinam alone, none reaches the published band and the cohort sits slightly worse than a random draw. A structural screen over molecular data does find them, all six from a shortlist of 26. [Both measurements are below](#the-anchor-case-and-why-it-is-still-a-miss).

## Architecture

```
public data (KEMI, EU Pesticides DB, ECHA, EFSA, SGU, Europe PMC)
    -> scheduled dated snapshots of registers that publish current state only
    -> ingestion + entity resolution (CAS/EC, PubChem/ChEBI, AGROVOC)
    -> temporal knowledge graph (known_at on every fact and edge)
    -> ML: early-warning ranking, link prediction, anomaly detection
    -> explainability: evidence paths and SHAP over a tabular baseline
    -> interfaces (reports, BI, API)
```

```
src/hazium/
├── sources/     ingestion adapters, one per agency or registry
├── resolve/     entity resolution across vocabularies
├── graph/       knowledge graph construction and as_of queries
├── ml/          tasks, tabular baselines, embeddings
├── benchmark/   HEWB, the versioned early-warning benchmark
├── explain/     evidence paths and SHAP
└── snapshots/   dated capture of current-state-only sources
pipeline/        numbered pipeline scripts (01_, 02_, ...)
tests/
```

## Principles

The full set is in [MANIFESTO.md](MANIFESTO.md). The three that shape the code most:

- **The baseline rule.** Every graph or deep model is compared against a tabular gradient-boosting baseline on the identical task and split. If it does not win, the baseline is the published result.
- **Explainability is mandatory.** The system never outputs "high risk" without a traceable evidence path to source documents.
- **Temporal integrity.** Time-based splits only. A retrospective claim without `known_at` discipline is invalid.

## Roadmap

The V-ladder is the capability ladder. HEWB, the Hazium Early Warning Benchmark, is orthogonal to it: the versioned measuring stick every version reports against, so results stay comparable across methods.

| Version | Deliverable | State |
|---|---|---|
| V0 | Knowledge graph: ingestion, entity resolution, evidence-path queries | Done |
| V1 | ML tasks, tabular baselines, SHAP, time-split retrodetection eval | Done |
| V1.5 | Discrete-time survival panel: one approved substance per year at risk, so approval age becomes the baseline hazard rather than a competing feature. Evidence adds +0.140 AP over age alone (p = 0.024) | Done, and the current basis of the watchlist |
| V2 | Node embeddings on the same tasks | Documented negative, re-tested on the survival panel where coverage doubles to 65.3%. They lose by more there: 0.242 to 0.176 |
| V3 | GNNs with evidence-path explanations | Not entered, per the V2 gate |
| V4 | Second domain. Four candidate EU regimes gated against the method's three preconditions, each failing differently: PFAS (unbounded population, circular hazard-defined labels), biocides (42% dual-use with pesticides, 15 independent positives), food additives (~4 clean safety withdrawals, calendar-driven review), feed additives (309 positives but 61% are commercial non-reapplications). No second domain claimed; the boundary is the result | Gated, not entered |
| HEWB v1.4 | Versioned early-warning benchmark, released with a robustness capstone: annual rolling-origin eval, per-case lead-time, and a label-shuffle kill-criterion | Released |

## Results

The frozen v1.4 benchmark, its result tables, and the full robustness evidence are packaged as a citable dataset in [`release/hewb-v1.4/`](release/hewb-v1.4/).

HEWB fixes ten historical EU pesticide bans and asks, at each annual cutoff from 2009, where Hazium would have ranked each substance using only evidence dated before that cutoff. Lead time is measured in months between the earliest cutoff a substance enters the top-k and the real regulatory action.

Using only pre-cutoff data across **2009-2024**, XGBoost reaches average precision 0.254 at the 2023-01-01 cutoff, on 25 positives in 5,933 substances. It ranked the real EU-banned substances years before the ban:

- **Chlorpyrifos**: flagged 132 months (11 years) before its 2020 EU ban, at k=10.
- **Mancozeb**: in the top-20 from 2010, about nine years before its 2021 non-renewal.
- **9 of 10** headline landmark cases flag within the top-50 at some cutoff, and **7 of the 10** do so ahead of the EU's own first regulatory action, not merely before the final ban. Epoxiconazole is the one the model never flags.

Out-of-fold scores are averaged over repeated cross-validation, so lead-times are reproducible rather than an artifact of one fold split.

The feature set spans six groups, each grounded in a dated public source: EU hazard classifications (ECHA CLP), EFSA assessment history, Swedish sales trends (KEMI), graph structure, scientific-literature volume (Europe PMC), and ECHA CLH-intention status.

SHAP puts the independent scientific-literature feature second overall. It carries as much weight as the in-funnel regulatory-concern signals rather than more. The single largest driver is an approval-age prior, reported and mitigated separately with cohort-relative ranking.

## The approval-age baseline beats the model

The headline above is real but it is not the interesting number, and the
comparison that produced it was against the wrong baselines.

For a long time the trivial baselines here were severe-hazard count, sales
tonnage and assessment count. All three are weak, and the learned model beat
them by roughly an order of magnitude. Approval age was never tested on its own,
because it sat inside the model as a feature.

Ranking substances on nothing but how long they have held EU approval reaches
**98% of the full model's mean average precision** across the sixteen cutoffs,
wins outright at **11 of 16**, and reproduces the headline lead times exactly:
chlorpyrifos at 132 months, thiacloprid at 133, clothianidin at 120, propikonazol
at 119. On chlorpyrifos-methyl and mancozeb it does better than the model.
Dropping the two approval-age features leaves the model at **37%** of its
performance.

| | XGBoost | approval age (1 feature) |
|---|---|---|
| landmarks flagged, k=50 | 9 of 10 | 8 of 10 |
| mean AP across 16 cutoffs | 0.467 | 0.459 |
| cutoffs won | 5 of 16 | 11 of 16 |

The mechanism is structural rather than a bug. A substance can only be
non-renewed when its approval comes up for renewal, and approval age proxies
proximity to that decision, so the ranking substantially answers *whose turn it
is* rather than *who fails*. Approval date is knowable at every cutoff, so this
is not leakage; it is a different question from the one the benchmark was built
to ask.

The six evidence groups are therefore worth, over a date subtraction, one extra
landmark out of ten and 0.008 average precision. `approval_age` is now reported
as a trivial baseline rather than hidden inside the model, and by this project's
own baseline rule it is the published result until a learned model beats it.

**Robustness.** Four tests harden the headline (raw outputs in `release/hewb-v1.4/`). A label-shuffle placebo, the project's kill-criterion, collapses to the base rate on permuted labels: real average precision 0.230 against a shuffled maximum of 0.013 over 50 permutations, p = 0.020. The signal is real rather than small-class overfitting. The lead over the hazard, sales and assessment baselines holds at every cutoff from 2020 to 2024, so 2023 is not a selected result; the lead over approval age does not, as above. Substances that went through EU review and stayed approved rank well below the true positives, and hazardous-but-never-actioned substances put zero cases in the top 10. The model is specific rather than flagging whatever looks dangerous.

**The anchor case, fluazinam.** Under the headline EU-non-renewal label it ranks in the top 5% (269th of 5,933) on its general hazard and sales profile but stays outside the strict top-50 bar. Its actual concern is groundwater: fluazinam breaks down into the PFAS substance trifluoroacetic acid (TFA), which spreads to groundwater. Kemikalieinspektionen opened a formal reevaluation of the TFA-forming actives on 2025-11-20 (decision due by April 2028), and an SVT Granskning investigation brought it to national attention in July 2026. The EU-regulatory, hazard, and sales sources do not cover groundwater or residue monitoring, so that signal sits outside the current data. Under a second label variant that also counts that Swedish national reevaluation, fluazinam becomes a positive and ranks in the top 4% (206th of 5,933) out-of-fold, the closest result yet to the north-star question.

The concern has since been confirmed independently, after the fact. A national SGU groundwater investigation across 2023-2025 found TFA at 91% of 237 sites (median 230 ng/l), tied to fluorinated plant-protection breakdown. Sweden's historical pesticide monitoring meanwhile records fluazinam itself at 0 of 139 groundwater analyses, because the parent degrades to TFA before it reaches groundwater. That monitoring post-dates every benchmark cutoff, so it is not a model input; folding groundwater and residue monitoring in as a present-day signal is the next step on the roadmap.

**V2, node embeddings.** metapath2vec embeddings, run alone and concatenated with the tabular features on the identical split, lose at every cutoff. Only 29.2% of the population has any walkable graph structure, so the embedding is a constant zero vector for the rest and dilutes the signal. V3 (GNN) is not entered: message-passing would hit the same coverage ceiling.

## The question was wrong, and fixing it recovered the model

The approval-age result above says the binary target was doing very little work.
It does not follow that the evidence is worthless, and testing that properly is
what produced the main result of the project.

"Was this substance ever withdrawn" is asked over a population that is 96%
substances never approved in the EU, which therefore could never be withdrawn at
all. Answering it is mostly an eligibility test, and approval age performs that
test. The target mixes *whether* a withdrawal happened with *when*, and time
wins.

The separable question is asked on a discrete-time survival panel: one approved
substance in one year at risk, outcome inside a horizon starting that year.
Approval age becomes the baseline hazard, which is what it is, and the evidence
is left to explain the rest. On that panel, with folds grouped by substance:

| arm | average precision | lift over base rate | AUC |
|---|---|---|---|
| approval age alone | 0.102 | 3.6x | 0.836 |
| evidence alone | 0.180 | 6.3x | 0.753 |
| **age + evidence** | **0.242** | **8.4x** | **0.880** |

The gain is +0.140 against a seed spread of ±0.029. Three checks back it: the
signal survives lagging every feature by three years, decaying from +0.124 to
+0.026 rather than collapsing, so it is not an artefact of activity immediately
before a decision; a block permutation over whole substance histories puts it at
**p = 0.024**; and in a genuine forward split, fit on 2019 and earlier and scored
on 2020 onward, the top 50 contains **11 real withdrawals against approval age's
4**. At the three-year horizon every one of the nine forward splits is positive.

A fourth check was published here and was wrong. Approval age was reported as
*not* recoverable from the evidence (R² = −0.009), which would have made the two
arms independent. That R² came from an unshuffled `KFold` on a panel built year
by year and concatenated, so it split on time and tested on years whose approval
ages lay outside the training range. Grouped by substance the real answer is
**+0.47**: the evidence encodes roughly half of approval age, and "evidence only"
is not an age-free arm. The headline comparison is unaffected, because both arms
are given the age features explicitly, so the +0.140 is measured over and above
age either way.

The limits are equally measurable and equally published. A linear model recovers
about a fifth of what gradient boosting does, so the effect lives in
interactions. 75 of the 102 events fall in the 2017-2021 renewal wave, and that
is the binding constraint: a model fitted before the wave does not transfer into
it. Raw scores are badly calibrated and must not be read as probabilities. Run
the result with `pipeline/28_run_survival.py` and every check above with
`pipeline/32_verify_survival.py`.

## The anchor case, and why it is still a miss

The north-star question above has a measurable answer now, and the answer is no.

Asked of fluazinam alone it is not answerable. Any ranking puts some substance
somewhere, and at an earlier stage of this work fluazinam sat at 96 of 260 and
inside the published band, which reads as a hit. It is 117 today, and neither
number means anything on its own.

Kemikalieinspektionen named **six** TFA-forming substances in the same
reevaluation on 2025-11-20. That cohort is dated, externally defined, and chosen
by a regulator rather than by this project, which makes it a test. Their
positions in the v2 three-year ranking of the 260 substances still at risk:

| substance | rank of 260 |
|---|---|
| Fluazinam | 117 |
| Flonicamid | 128 |
| Diflufenican | 146 |
| Fluopyram | 190 |
| Mefentrifluconazole | 213 |
| tau-fluvalinate | 225 |

**None of the six reaches the published top 100, where chance alone would put
2.3 of them.** The cohort median sits at the 65th percentile, slightly worse
than a random draw. There is no reading of this in which the model anticipated
the reevaluation.

The cause is the input set, not the target. TFA is a degradation product, and
the hazard appears in groundwater monitoring, which is not among the ingested
sources. An approval record, a hazard classification and a sales table do not
say that a substance becomes something persistent after it leaves the field, so
no reformulation of the target can recover a signal that is not in the features.
Folding groundwater and residue monitoring in is the next data source on the
roadmap, and this cohort is the test it has to pass.

The announcement itself is in the graph and is *not* visible to the model:
`pipeline/03` merges KEMI announcements as `SUBJECT_OF` edges, which no feature
group reads. Rebuilding the feature matrix with those six nodes removed changes
nothing for any of the 8,734 substances, so the ranking above is not circular.

Reported by `pipeline/32_verify_survival.py` via `benchmark/anchor.py`, which
exists so that the cohort rather than the convenient member is what gets quoted.

## The screen that finds it

The model predicts a committee decision. TFA formation is a chemical property.
Those come apart, and the anchor cohort is where they come apart visibly, so the
second artifact is not a model at all.

TFA comes from trifluoromethyl groups. A molecular formula is public, free from
PubChem, and identical at every cutoff, so it cannot leak and it is not the
regulator's opinion. Screening the 242 approved substances with a resolved
structure on that one rule:

| | |
|---|---|
| flagged as TFA precursors | **26 of 242** (10.7%) |
| of KEMI's six | **6 of 6**, where chance places 0.6 |
| hypergeometric p | **8.8e-7**, one in 1.1 million |
| fluazinam's rank | **1** |

Two checks, neither an input. KEMI named six on 2025-11-20 and all six are in
the shortlist. Separately, EFSA's own degradation records already list TFA as a
metabolite for flutolanil, which the rule flags without being told.

The weights are written down in `screen/tfa.py` rather than fitted. Six confirmed
substances can check a rule and cannot train one, so fitting on them and then
reporting how well the fit ranks them would measure nothing.

It is a screen, so it is deliberately wide: 20 of the 26 carry no published TFA
finding from any regulator. Six more substances carry difluoromethyl rather than
trifluoromethyl and are excluded, since those degrade toward difluoroacetic acid,
a related concern and a different compound. Eighteen have no PubChem structure
and are left out of the population rather than counted as clean.

Run it with `pipeline/34_ingest_structures.py` then `pipeline/35_run_tfa_screen.py`.
Structures are committed under `data/raw/`, so the screen runs offline and scores
the same molecules a reviewer can read.

## The forward watchlist

Every result above is retrospective: the model is graded against regulatory
actions that already happened. One surface on the site is not. `pipeline/30`
scores today's approved substances with the survival model, and `pipeline/25`
through `27` turn that ranking into something that can be marked. It replaced
`pipeline/13`, which used the binary target and therefore mostly returned old
approvals: moving to the survival ranking drops the two most obvious false
positives, a fatty-acid soap and acetic acid, from 5th and 62nd to 30th and
147th.

Two things make it falsifiable rather than an assertion. Every EU approval
carries an expiry date on which the Commission is forced to decide, so each
entry has a deadline: 64 of the 98 tracked substances reach theirs by the end of
2027. And `pipeline/26_track_resolution.py` records what the register said when
the prediction was made, then classifies each outcome afterwards as a lapse, a
full-term renewal (which confirms a false positive) or a short procedural
extension (which settles nothing and is counted as still open). Collapsing the
third into the second is what makes an early-warning model look worse than it is.

The ranking is also mapped onto the crops it reaches, through KemI's Swedish
product register: 32 of the top 100 are in currently approved plant protection
products. No product or brand is named. A large share of any list this length is
never actioned, so naming commercial products against it would put specific
companies on a list carrying that error.

## Provenance archive

Several sources publish current state and keep no history, so a fact read today
cannot be placed at a past cutoff without leaking. `hazium.snapshots` fixes that
going forward rather than pretending it away: a monthly GitHub Action captures
each source and stamps it with the date of capture, which becomes the `known_at`
of anything derived from it. Content-addressed storage keeps repeated captures of
a slow-moving register almost free, and failures are recorded rather than
discarded, because a gap in the archive matters when reading it later.

Four sources are captured, each with a stated future use. EU Pesticides Database
per-substance details date the Candidate-for-Substitution and ADI fields that the
bulk export publishes undated. SGU groundwater chemistry is CAS-coded and is the
fluazinam/TFA gap-closer, usable as a pre-cutoff feature from roughly 2029. The
other two are KEMI sales reports and the EFSA OpenFoodTox release metadata. ECHA is deliberately
excluded: it returns 403 to programmatic clients, and a collector that silently
fails every month is worse than none.

## License

Code is [AGPL-3.0](LICENSE). It is copyleft on purpose: anyone may study, run and build on it, but a modified version offered to others over a network has to publish its source. That keeps the work open without leaving it open to being taken proprietary.

The benchmark release in [`release/hewb-v1.4/`](release/hewb-v1.4/) is CC-BY-4.0, licensed separately because it is data rather than software; see its own [LICENSE](release/hewb-v1.4/LICENSE). An open, citable benchmark is worth more than a restricted one.

Copyright is held solely by Martin Blomqvist, who is not bound by the AGPL and may license the work on other terms. If the AGPL does not suit your use, write to <cm.blomqvist@gmail.com>.

The underlying facts come from public sources (EU Pesticides Database, ECHA, EFSA, Kemikalieinspektionen, SGU, Europe PMC) that carry their own terms.

---

*Hazium: from hazard. A fictional element, because the periodic table of public evidence is missing one.*
