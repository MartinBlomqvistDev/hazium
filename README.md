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
| V4 | Second domain (PFAS, via a shared-metabolite bridge to TFA) | Planned |
| HEWB v1.4 | Versioned early-warning benchmark: annual rolling-origin eval and per-case lead-time | Met |

## Results

HEWB fixes ten historical EU pesticide bans and asks, at each annual cutoff from 2009, where Hazium would have ranked each substance using only evidence dated before that cutoff. Lead time is measured in months between the earliest cutoff a substance enters the top-k and the real regulatory action.

Using only pre-cutoff data across **2009-2024**, XGBoost beats every trivial baseline at every cutoff (2023-01-01: average precision 0.254 against 0.016 for the best trivial ranker, on 25 positives in 5,933 substances). It ranked the real EU-banned substances years before the ban:

- **Chlorpyrifos**: flagged 132 months (11 years) before its 2020 EU ban, at k=10.
- **Mancozeb**: in the top-20 from 2010, about nine years before its 2021 non-renewal.
- **9 of 10** headline landmark cases flag within the top-50 at some cutoff, and **7 of the 10** do so ahead of the EU's own first regulatory action, not merely before the final ban. Epoxiconazole is the one the model never flags.

Out-of-fold scores are averaged over repeated cross-validation, so lead-times are reproducible rather than an artifact of one fold split.

The feature set spans six groups, each grounded in a dated public source: EU hazard classifications (ECHA CLP), EFSA assessment history, Swedish sales trends (KEMI), graph structure, scientific-literature volume (Europe PMC), and ECHA CLH-intention status. SHAP attributes the ranking to the independent literature signal well above the in-funnel regulatory features.

**The anchor case, fluazinam.** Under the headline EU-non-renewal label it ranks in the top 5% (269th of 5,933) on its general hazard and sales profile but stays outside the strict top-50 bar. Its actual concern is groundwater: fluazinam breaks down into the PFAS substance trifluoroacetic acid (TFA), which spreads to groundwater. Kemikalieinspektionen opened a formal reevaluation of the TFA-forming actives on 2025-11-20 (decision due by April 2028), and an SVT Granskning investigation brought it to national attention in July 2026. The EU-regulatory, hazard, and sales sources do not cover groundwater or residue monitoring; that is the next data source on the roadmap. Under a second label variant that also counts that Swedish national reevaluation, fluazinam becomes a positive and ranks in the top 4% (206th of 5,933) out-of-fold, the closest result yet to the north-star question.

**V2, node embeddings.** metapath2vec embeddings, run alone and concatenated with the tabular features on the identical split, lose at every cutoff. Only 29.2% of the population has any walkable graph structure, so the embedding is a constant zero vector for the rest and dilutes the signal. V3 (GNN) is not entered: message-passing would hit the same coverage ceiling.

---

*Hazium: from hazard. A fictional element, because the periodic table of public evidence is missing one.*
