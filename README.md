# Hazium

> Tracing systemic exposure.

Hazium is an explainable machine learning platform that constructs a temporally-aware knowledge graph of environmental and public health evidence from heterogeneous public data: regulatory decisions, hazard classifications, national sales statistics, residue monitoring and scientific conclusions. Machine learning over that graph produces early-warning signals; every signal is traceable back to source evidence.

The first domain is pesticides, with a Nordic focus. The intelligence comes from ML. LLMs are presentation only.

## The north-star question

> Using only data known before 2023-01-01, does Hazium rank fluazinam, the fungicide at the centre of Sweden's 2026 pesticide controversy, among the highest-concern substances approved in Sweden?

Every version of the system is measured against this retrodetection question under strict temporal discipline: every fact and every edge carries a `known_at` timestamp, and models never see evidence dated after the evaluation cutoff.

## Architecture

```
public data (KEMI, EU Pesticides DB, ECHA, EFSA, SLV)
    → ingestion + entity resolution (CAS/EC, PubChem/ChEBI, AGROVOC)
    → temporal knowledge graph (Postgres source of truth → PyTorch Geometric)
    → ML tasks: link prediction · early-warning ranking · anomaly detection
    → explainability: evidence paths · SHAP baselines
    → interfaces (reports, BI, API)
```

## Repository layout

```
├── MANIFESTO.md          project constitution — read this first
├── CLAUDE.md             working rules for AI-assisted development
├── src/hazium/
│   ├── sources/          ingestion adapters (one per agency/registry)
│   ├── resolve/          entity resolution across vocabularies
│   ├── graph/            knowledge graph construction and queries
│   ├── ml/               tasks, baselines, embeddings, GNNs
│   └── explain/          evidence paths, SHAP, explainer comparisons
├── pipeline/             numbered pipeline scripts (01_, 02_, ...)
├── tests/
├── notebooks/            exploration only — nothing load-bearing lives here
└── data/                 local data snapshots (gitignored)
```

## Principles

The full constitution is in [MANIFESTO.md](MANIFESTO.md). The three that shape the code most:

- **The baseline rule.** Every graph or deep model is compared against a tabular gradient-boosting baseline on the identical task and split. If it does not win, the baseline is the published result.
- **Explainability is mandatory.** The system never outputs "high risk" without a traceable evidence path to source documents.
- **Temporal integrity.** Time-based splits only. A retrospective claim without `known_at` discipline is invalid.

## Roadmap

| Version | Deliverable | Gate |
|---|---|---|
| V0 | Knowledge graph: ingestion, entity resolution, evidence-path queries | Fluazinam evidence graph reconstructable and traversable |
| V1 | Defined ML tasks, tabular baselines, SHAP, time-split retrodetection eval | Published eval table |
| V2 | Node embeddings on the same tasks | Beats V1 baseline, or the negative result is documented |
| V3 | GNNs with evidence-path explanations | Entered only if V2 shows signal |
| V4 | Second domain (PFAS, via the fluazinam→TFA edge) | Two domains share one architecture |

## Status

**V0 — knowledge graph construction.** In progress. The fluazinam evidence
graph is reconstructable and traversable from real ingested data; the
remaining V0 work adds the dated toxicological evidence the retrodetection
eval depends on.

| V0 component | State |
|---|---|
| Temporal data contracts (`known_at` on every fact) | Done |
| Evidence-path graph with `as_of` views | Done |
| KEMI sales adapter (annual report PDFs) | Done |
| KEMI register adapter (JSON API, products + CAS) | Done |
| Substance entity resolution (name → CAS) | Done |
| Register structure graph (`CONTAINS`, `APPROVED_IN`) | Done |
| EFSA / CLP adapter (`CLASSIFIED_AS`, `DEGRADES_TO`, dated events) | Next |

The gate (*fluazinam reconstructable and traversable*) is met on KEMI
structure; the fluazinam→TFA degradation edge and hazard classifications
arrive with the EFSA adapter. See [`DEV_LOG.md`](DEV_LOG.md) for the full
build record and the reasoning behind each decision.

---

*Hazium: from hazard. A fictional element, because the periodic table of public evidence is missing one.*
