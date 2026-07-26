# HAZIUM

> Tracing systemic exposure.

*Building computational models that help humans investigate environmental and public health hazards.*

**Manifesto, version 0.4. A living document.** Every significant architectural decision in this repository should be traceable to a principle stated here. If evidence shows a principle is wrong, revise the principle, not just the implementation.

---

## 1. Why Hazium exists

Hazium began with a simple question: could publicly available data have revealed the Swedish fluazinam controversy before it became national news?

The obvious answer was a watchlist. Investigation revealed a more fundamental problem. Europe does not lack environmental data; it possesses enormous quantities of scientific, toxicological, regulatory and monitoring information. The problem is that this knowledge exists in isolation. Scientific publications exist separately from regulatory decisions. Sales statistics exist separately from exposure pathways. Residue measurements exist separately from health research. Each source describes a fragment; none can explain the whole.

Hazium therefore asks a different question: **can machine learning construct representations that make relationships across heterogeneous public evidence discoverable, explainable and investigable?**

The objective is not automation. The objective is understanding.

## 2. What Hazium is, and is not

Hazium is an explainable machine learning platform. It continuously constructs an investigable computational representation of environmental and public health evidence, with the ambition of surfacing emerging hazards before they become widely recognised.

Hazium is **not** a pesticide database, a watchlist, a dashboard, a news aggregator, a compliance tool, or a replacement for regulatory agencies. Any of these may become interfaces. None of them are the product.

Its first domain is pesticides, with a Nordic focus. This choice is pragmatic: the data is open, the ground truth is recent, and the first validated case (fluazinam) lives there.

## 3. First principles

**Reality is relational.** Hazards do not exist as isolated observations. A substance connects to metabolites, crops, residues, papers, classifications and regulatory decisions. The relationships are the signal.

**Evidence is distributed.** No single organisation possesses complete knowledge. Understanding emerges through synthesis of independent observations.

**Models are investigative instruments.** The purpose of modelling is reasoning, not visualisation. Visualisations are outputs; the model is the product.

**AI augments judgement.** Hazium supports human investigation. It never automates conclusions, and it is not a scientific authority.

**Every conclusion must be explainable.** The system never outputs "this substance is high risk." It outputs "this substance resembles previously problematic substances *because*", with a traceable evidence path. Opacity is a design failure.

**Technology follows purpose.** A technology is introduced only when it improves the system's ability to represent or reason about reality. Portfolio value is never sufficient justification. Every choice must be defensible against its alternatives, including the alternative of not using it.

**Honesty over novelty.** Every learned model is evaluated against a simple baseline on the same task. A negative result, honestly reported, is a valid deliverable.

**Temporal integrity.** Every fact and every edge carries a `known_at` timestamp. Evaluation uses time-based splits only: a model claiming it could have detected a hazard in year T may see nothing dated after T. Without this discipline, every retrospective claim is invalid.

## 4. The north-star evaluation, and the Hazium Early Warning Benchmark (HEWB)

One falsifiable question anchors the project:

> **Using only data with `known_at` before 2023-01-01, does Hazium rank fluazinam among the highest-concern substances approved in Sweden?**

The question has an answer, and it is instructive. HEWB does not rank fluazinam highly, and neither does its survival successor: asked of all six TFA-forming substances Kemikalieinspektionen opened for reevaluation on 2025-11-20, none reaches the published band and the cohort sits slightly worse than a random draw. The hazard is a degradation product, visible in groundwater monitoring and absent from every regulatory record the benchmark reads, so a model over those records cannot express it. A screen over molecular structure can: one rule about trifluoromethyl groups narrows 242 approved substances to 26, and all six are inside. That is the boundary between the two artifacts this project publishes. **A benchmark measures a model against a target; a screen applies a stated rule where no model can be fitted.** Six confirmed substances can check a rule and cannot train one, so the screen's weights are written down rather than estimated, and the cohort is held out rather than used.

This question is no longer answered by one case in isolation. It is formalised as the **Hazium Early Warning Benchmark (HEWB)**: a versioned, reproducible evaluation program that every model reports against. That covers everything from a trivial baseline to a tabular model, a graph model, or a future architecture. HEWB fixes three things: a set of historical EU regulatory actions, a temporal-evaluation protocol under strict `known_at` discipline, and a **lead-time** metric. Lead time asks not merely whether a substance ranks highly, but how many months before the real regulatory action it would have. A result is comparable to another only if both ran the same frozen HEWB version.

HEWB v1.4 measures lead time against ten landmark EU non-renewals over an annual cutoff schedule from 2009. The tabular feature set spans EU hazard classifications, EFSA assessment history, Swedish sales trends, graph structure, scientific-literature volume (Europe PMC), and ECHA CLH-intention status. At k=10 the model ranks chlorpyrifos 132 months before its EU ban; mancozeb enters the top-20 from 2010, about nine years before its 2021 non-renewal. Nine of ten landmarks flag within the top-50 at some cutoff. Seven of the ten do so ahead of the EU's own first regulatory action rather than merely before the final ban, and epoxiconazole is the one the model does not flag. Out-of-fold scores are averaged over repeated cross-validation, so lead-times are reproducible rather than an artifact of one fold split. The 2023-01-01 headline average precision is 0.254. That figure was long reported as an order of magnitude above the trivial baselines, which was true only because approval age had never been tested as one: ranking on approval age alone reaches 98% of the model's mean average precision and wins at 11 of 16 cutoffs, so by §3's baseline rule the baseline is the published result until a learned model beats it. SHAP puts the independent literature signal second overall, on par with the in-funnel regulatory features rather than above them; the single largest driver is an approval-age prior, reported and mitigated separately. Graph embeddings (Node2Vec-style structural representations) were run against this baseline and lose. That negative was first attributed to coverage: only 29.2% of the full population had walkable graph structure, so the embedding was a constant zero vector for the rest, which is a fixable-sounding excuse rather than a finding. It has since been re-tested on the survival panel, where the population is approved substances only and embedding coverage rises to 65.3%, with the embeddings refit per year against that year's `as_of` view. They still lose, and by more: adding them to the tabular model moves average precision from 0.242 to 0.176, against a seed tolerance of 0.029, and on their own they reach AUC 0.548, which is close to random. Thirty-two extra dimensions dilute a 102-event signal. The V2 gate stays closed, now for a reason that survives the coverage objection.

Every version of the system is measured against HEWB. Ambition without falsifiability is decoration.

The same rule binds the forward watchlist, which is the only claim here about a future that has not happened. It is published with each substance's approval expiry attached, because that date is when the Commission must decide and therefore when the claim becomes checkable. A prediction without a deadline cannot be marked, and an unmarkable prediction is decoration too.

## 5. Position among prior work

Hazium is not the first system to reason over chemical hazard knowledge graphs, and pretending otherwise would be a credibility failure.

- **ComptoxAI** (University of Pennsylvania) builds a knowledge graph with graph neural networks for computational toxicology. It validates the core approach.
- **Tox21 / chemprop** represent the molecular deep learning tradition: predicting toxicity from chemical structure.
- **EWG, PAN Europe** and similar organisations publish curated watchlists and campaign reports.

Hazium's differentiation is deliberate: it fuses **regulatory and market evidence** (sales trends, residue monitoring, approval events, re-evaluation status) with toxicological knowledge, in a **Nordic/EU public-data context**, aimed at **early warning** rather than laboratory toxicology. Where prior work predicts what a molecule does, Hazium investigates what the evidence, taken together, already suggests.

## 6. Machine learning philosophy

**Tasks before methods.** No architecture enters the codebase without a defined task and evaluation. The initial task set:

1. **Link prediction**: predict missing substance-to-hazard edges from graph structure (shared metabolites, structural neighbours, co-citation).
2. **Ranking / early warning**: rank substances by likelihood of future regulatory action. The positive class is small (tens of cases); this is few-label, ranking-oriented territory, and the methodology must respect that.
3. **Anomaly detection**: changepoints and outliers in national sales and residue time series.

**The baseline rule.** Every graph or deep model is compared against a tabular gradient-boosting baseline on the identical task and split. If it does not win, the baseline is the published result. Method ladders (Node2Vec, GraphSAGE, attention-based GNNs) are hypotheses to test, not milestones to check off.

**LLMs are presentation.** Large language models generate summaries and translations of results the ML layer has already produced and the evidence layer can already justify. They contribute no intelligence to the platform.

## 7. Explainability

In order of primacy:

1. **Evidence paths.** Every ranking or prediction is traceable through the graph to source documents: the metapath is the explanation.
2. **SHAP** on tabular baselines.
3. **Post-hoc GNN explainers** (GNNExplainer, PGExplainer) as comparison experiments only. Attention weights are not treated as explanations.

## 8. The graph

The knowledge graph is the world model, not a database choice. It is constructed from a relational source of truth and materialised as a learning representation. Identity comes from existing vocabularies (CAS/EC numbers, PubChem/ChEBI identifiers, AGROVOC crop terms); Hazium does not invent an ontology. Entity resolution across agencies is treated as a first-class engineering problem, because knowledge graphs fail at their joins, not at their models.

## 9. Domain trajectory

The architecture becomes domain-agnostic **by evolution, not by upfront design**. Version zero is built for pesticides without apology.

PFAS was the intended second domain, entered through a degradation edge the first domain already contains: EFSA's OpenFoodTox data verifies three fungicides (flufenacet, flutolanil, flurtamone) converging on trifluoroacetic acid, a PFAS compound. That edge is real and it stays. The domain does not. Measured against the method's three preconditions, PFAS fails two of them. The population is unbounded rather than a registry of a few thousand. The labels are hazard-defined rather than the outcome of a dated approval-review-withdrawal pipeline, which makes them circular. Fluazinam's own suspected TFA link, the reason it made national news, is not yet in any ingested dataset and is not asserted until a dated source supports it. The bridge stands on what is verified, not on the specific case that motivated the search for it.

Three further regimes were gated the same way and failed differently. Biocides are 42% dual-use with pesticides, leaving 15 independent positives. Food additives yield roughly four clean safety withdrawals, and their review is driven by calendar rather than concern. Feed additives have 309 positives, but 61% are flavourings nobody reapplied for, so the label measures commercial abandonment rather than risk. **No second domain is claimed. The mapped boundary is the result.**

This is the section working as intended rather than failing. Only when two domains coexist are the shared abstractions extracted. Premature generality is a known failure mode, and this document forbids it; four documented negatives are what obeying that looks like.

Candidate future domains: endocrine disruptors, pharmaceuticals in waterways, antibiotic resistance, heavy metals, drinking water contaminants, air pollution, hazards not yet recognised today.

## 10. What would falsify this project

- The retrodetection evaluation cannot be made temporally sound with available data.
- No learned model beats simple baselines on any defined task, and the baselines themselves add nothing over existing watchlists.
- The evidence paths produced are not, in the judgement of a domain-literate reader, genuine explanations.

If these hold after honest effort, the correct output is a write-up saying so.

## 11. Roadmap

HEWB (§4) is orthogonal to this ladder: the versioned measuring stick every version below reports against, not a rung on it.

| Version | Deliverable | Gate |
|---|---|---|
| V0 | Knowledge graph construction: ingestion, entity resolution, `known_at` on every edge, evidence-path queries | The fluazinam evidence graph can be reconstructed and traversed |
| V1 | Defined tasks, tabular baselines, SHAP, time-split retrodetection eval | Published eval table |
| V2 | Node embeddings (Node2Vec) on the same tasks | Beats V1 baseline, or the negative result is documented |
| V3 | GNNs (GraphSAGE, then attention variants), evidence-path explanations | Only entered if V2 shows signal |
| V4 | Second domain, extraction of domain-agnostic abstractions | Two domains share one architecture. Four candidates gated (PFAS, biocides, food additives, feed additives), all four failed a precondition, so the gate held and the boundary is published instead |

---

*Hazium: from hazard. A fictional element, because the periodic table of public evidence is missing one.*
