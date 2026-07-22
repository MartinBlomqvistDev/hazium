# Hazium

[![CI](https://github.com/MartinBlomqvistDev/hazium/actions/workflows/ci.yml/badge.svg)](https://github.com/MartinBlomqvistDev/hazium/actions/workflows/ci.yml)

> Tracing systemic exposure.

Hazium is an explainable machine learning platform that builds a temporally-aware knowledge graph of environmental and public-health evidence from heterogeneous public data: regulatory decisions, hazard classifications, national sales statistics, residue monitoring, and scientific conclusions. Machine learning over that graph ranks substances for future regulatory risk, and every signal traces back to the source evidence behind it.

The first domain is pesticides, with a Nordic focus. The intelligence is in the ML; large language models are used for presentation only.

## The north-star question

> Using only data known before 2023-01-01, does Hazium rank fluazinam, the fungicide at the centre of Sweden's 2026 pesticide controversy, among the highest-concern substances approved in Sweden?

Every version of the system is measured against this retrodetection question under strict temporal discipline. Every fact and every edge carries a `known_at` timestamp, and a model evaluated at a given cutoff never sees evidence dated on or after it.

## Architecture

```
public data (KEMI, EU Pesticides DB, ECHA, EFSA, Europe PMC)
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
└── explain/     evidence paths and SHAP
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
| V2 | Node embeddings on the same tasks | Documented negative |
| V3 | GNNs with evidence-path explanations | Not entered, per the V2 gate |
| V4 | Second domain. Four candidate EU regimes gated against the method's three preconditions, each failing differently: PFAS (unbounded population, circular hazard-defined labels), biocides (42% dual-use with pesticides, 15 independent positives), food additives (~4 clean safety withdrawals, calendar-driven review), feed additives (309 positives but 61% are commercial non-reapplications). No second domain claimed; the boundary is the result | Gated, not entered |
| HEWB v1.4 | Versioned early-warning benchmark, released with a robustness capstone: annual rolling-origin eval, per-case lead-time, and a label-shuffle kill-criterion | Released |

## Results

The frozen v1.4 benchmark, its result tables, and the full robustness evidence are packaged as a citable dataset in [`release/hewb-v1.4/`](release/hewb-v1.4/).

HEWB fixes ten historical EU pesticide bans and asks, at each annual cutoff from 2009, where Hazium would have ranked each substance using only evidence dated before that cutoff. Lead time is measured in months between the earliest cutoff a substance enters the top-k and the real regulatory action.

Using only pre-cutoff data across **2009-2024**, XGBoost beats every trivial baseline at every cutoff (2023-01-01: average precision 0.254 against 0.016 for the best trivial ranker, on 25 positives in 5,933 substances). It ranked the real EU-banned substances years before the ban:

- **Chlorpyrifos**: flagged 132 months (11 years) before its 2020 EU ban, at k=10.
- **Mancozeb**: in the top-20 from 2010, about nine years before its 2021 non-renewal.
- **9 of 10** headline landmark cases flag within the top-50 at some cutoff, and **7 of the 10** do so ahead of the EU's own first regulatory action, not merely before the final ban. Epoxiconazole is the one the model never flags.

Out-of-fold scores are averaged over repeated cross-validation, so lead-times are reproducible rather than an artifact of one fold split.

The feature set spans six groups, each grounded in a dated public source: EU hazard classifications (ECHA CLP), EFSA assessment history, Swedish sales trends (KEMI), graph structure, scientific-literature volume (Europe PMC), and ECHA CLH-intention status. SHAP puts the independent scientific-literature feature second overall, carrying as much weight as the in-funnel regulatory-concern signals rather than above them; the single largest driver is an approval-age prior, reported and mitigated separately with cohort-relative ranking.

**Robustness.** Four tests harden the headline (raw outputs in `release/hewb-v1.4/`). A label-shuffle placebo, the project's kill-criterion, collapses to the base rate on permuted labels (real average precision 0.230 against a shuffled maximum of 0.013 over 50 permutations, p = 0.020), so the signal is real rather than small-class overfitting. The lead over baseline holds at every cutoff from 2020 to 2024, so 2023 is not a selected result. Substances that went through EU review and stayed approved rank well below the true positives, and hazardous-but-never-actioned substances put zero cases in the top 10, so the model is specific rather than flagging whatever looks dangerous.

**The anchor case, fluazinam.** Under the headline EU-non-renewal label it ranks in the top 5% (269th of 5,933) on its general hazard and sales profile but stays outside the strict top-50 bar. Its actual concern is groundwater: fluazinam breaks down into the PFAS substance trifluoroacetic acid (TFA), which spreads to groundwater. Kemikalieinspektionen opened a formal reevaluation of the TFA-forming actives on 2025-11-20 (decision due by April 2028), and an SVT Granskning investigation brought it to national attention in July 2026. The EU-regulatory, hazard, and sales sources do not cover groundwater or residue monitoring, so that signal sits outside the current data. Under a second label variant that also counts that Swedish national reevaluation, fluazinam becomes a positive and ranks in the top 4% (206th of 5,933) out-of-fold, the closest result yet to the north-star question.

The concern has since been confirmed independently, after the fact: a national SGU groundwater investigation across 2023-2025 found TFA at 91% of 237 sites (median 230 ng/l), tied to fluorinated plant-protection breakdown, while Sweden's historical pesticide monitoring records fluazinam itself at 0 of 139 groundwater analyses (the parent degrades to TFA before it reaches groundwater). That monitoring post-dates every benchmark cutoff, so it is not a model input; folding groundwater and residue monitoring in as a present-day signal is the next step on the roadmap.

**V2, node embeddings.** metapath2vec embeddings, run alone and concatenated with the tabular features on the identical split, lose at every cutoff. Only 29.2% of the population has any walkable graph structure, so the embedding is a constant zero vector for the rest and dilutes the signal. V3 (GNN) is not entered: message-passing would hit the same coverage ceiling.

## License

Code is [AGPL-3.0](LICENSE). It is copyleft on purpose: anyone may study, run and build on it, but a modified version offered to others over a network has to publish its source. That keeps the work open without leaving it open to being taken proprietary.

The benchmark release in [`release/hewb-v1.4/`](release/hewb-v1.4/) is CC-BY-4.0, licensed separately because it is data rather than software; see its own [LICENSE](release/hewb-v1.4/LICENSE). An open, citable benchmark is worth more than a restricted one.

Copyright is held solely by Martin Blomqvist, who is not bound by the AGPL and may license the work on other terms. If the AGPL does not suit your use, write to <cm.blomqvist@gmail.com>.

The underlying facts come from public sources (EU Pesticides Database, ECHA, EFSA, Kemikalieinspektionen, SGU, Europe PMC) that carry their own terms.

---

*Hazium: from hazard. A fictional element, because the periodic table of public evidence is missing one.*
