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
├── TODO.md               current state and next step — read this to resume work
├── DEV_LOG.md            historical build record and decision rationale
├── V1_SCOPE.md           executable design doc for the V1 ML task
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
| V0 ✅ | Knowledge graph: ingestion, entity resolution, evidence-path queries | Fluazinam evidence graph reconstructable and traversable |
| V1 ✅ | Defined ML tasks, tabular baselines, SHAP, time-split retrodetection eval | Published eval table |
| V2 | Node embeddings on the same tasks | Beats V1 baseline, or the negative result is documented |
| V3 | GNNs with evidence-path explanations | Entered only if V2 shows signal |
| V4 | Second domain (PFAS, via a verified shared-metabolite bridge to TFA) | Two domains share one architecture |

## Status

**V0 and V1 gates both met.**

V0 — the fluazinam evidence graph is reconstructable and traversable from
real ingested data, carrying dated evidence and a dated hazard classification
that genuinely survive a pre-2023 `as_of` view: an EFSA conclusion from 2008,
and a CLP harmonised classification (Repr. 2, Aquatic Chronic 1, and four
other hazard codes) from 2015.

| V0 component | State |
|---|---|
| Temporal data contracts (`known_at` on every fact) | Done |
| Evidence-path graph with `as_of` views | Done |
| KEMI sales adapter (annual report PDFs) | Done |
| KEMI register adapter (JSON API, products + CAS) | Done |
| Substance entity resolution (name → CAS) | Done |
| Register structure graph (`CONTAINS`, `APPROVED_IN`) | Done |
| EFSA OpenFoodTox adapter (`DEGRADES_TO`, dated `EVIDENCED_BY`) | Done |
| ECHA CLP hazard classification (`CLASSIFIED_AS`) | Done |
| EU PPDB regulatory events (`SUBJECT_OF`; V1 label source) | Done |
| KEMI reevaluation announcements (Swedish national events) | Done |

V1 — a real, dated regulatory-action label (EU non-renewal events), a
temporally-clean feature set, and a rolling-origin backtest. **XGBoost beats
every trivial baseline at every cutoff** (2023-01-01: AP 0.183 vs. 0.016 best
trivial, on 25 positives out of 5,585 substances). Under this headline label,
fluazinam is an honest negative (ranks 5,271st of 5,585) — the EU-only
feature set has no signal for its actual 2026 concern (a national
TFA/groundwater finding).

A real Swedish signal was then found: Kemikalieinspektionen's 2025-11-20
national reevaluation of fluazinam (and five others) over TFA/groundwater
risk. Ingested and used to build a second, clearly-caveated label variant
(early-warning: also counts a Swedish reevaluation, not just an EU
non-renewal — a weaker, earlier signal, reported separately, never merged
into the headline table). **Under that variant, fluazinam becomes a genuine
positive and ranks 597th of 5,585 — top 10.7%, out-of-fold** — the closest
result yet to the project's own north-star question. Both results are
reported side by side, honestly caveated, every time the eval runs: see
[`V1_SCOPE.md`](V1_SCOPE.md) for the deliverable and [`DEV_LOG.md`](DEV_LOG.md)
for the full eval tables and reasoning.

See [`DEV_LOG.md`](DEV_LOG.md) for the full build record, including several
corrections and bugs found and fixed along the way: a scoping correction (the
fluazinam→TFA edge suggested by an early plan turned out not to exist in the
data; the verified alternative, a shared-metabolite bridge across three other
fungicides, is what actually ships), a temporal-correctness bug (a
substance's own node needs a dated fact to pull its `known_at` earlier, or it
never appears in an early `as_of` view no matter how well-dated its edges
are), and a silent feature bug in V1 (sales features were all-zero because
`SalesRecord.substance_id` needs entity resolution before it joins to the
graph). See [`TODO.md`](TODO.md) for the current next step and open
decisions.

---

*Hazium: from hazard. A fictional element, because the periodic table of public evidence is missing one.*
