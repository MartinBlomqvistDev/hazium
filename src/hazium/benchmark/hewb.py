"""The Hazium Early Warning Benchmark (HEWB) — the north-star made a
first-class, versioned, reproducible evaluation artifact.

See ``BENCHMARK_SCOPE.md`` for the full design. In short: the manifesto's
retrodetection question (``MANIFESTO.md`` §4) generalised from one case
(fluazinam) to a fixed set of historical EU regulatory actions, evaluated
under strict ``as_of`` temporal discipline, with a **lead-time** metric that
asks not merely "did the model rank this substance highly" but "how many
months *before* the real regulatory action would it have."

HEWB is not a roadmap version. The V-ladder (V0-V4) is the capability ladder;
HEWB is the measuring stick every version reports against. It carries its own
version line (``HEWB_VERSION``) so a result is only comparable to another if
both ran the same frozen benchmark.

Two layers:

* **Aggregate** — the existing rolling-origin backtest (``ml/baseline.py``)
  over the full non-renewal corpus, at *annual* cutoffs (finer than the V1
  eval's 2-year steps), against the trivial baselines and the tabular model.
  Reuses ``rolling_origin_eval``/``summarize`` unchanged; this module only
  fixes the cutoff schedule and pins the case set.
* **Case-study + lead-time** — a curated, individually-verified set of
  landmark regulatory actions, each with a lead-time in months and a full
  per-cutoff rank trajectory (the honest supporting evidence: even a landmark
  that never enters the top-k still shows *where* it ranked).

Everything here is pure over its inputs (a graph, sales, regulatory events) —
no I/O, no fetching. ``pipeline/12_run_hewb.py`` is the I/O boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from hazium.graph.store import TemporalGraph
from hazium.ml.baseline import CutoffResult, rolling_origin_eval
from hazium.ml.dataset import DEFAULT_POSITIVE_KINDS, EARLY_WARNING_POSITIVE_KINDS
from hazium.models import RegulatoryEvent, RegulatoryEventKind, SalesRecord

#: Bump on any change to the frozen configuration below (case set, cutoffs, k
#: values). A result labelled HEWB 1.0 is only comparable to another HEWB 1.0
#: result. Graph/data changes that move the numbers are a new minor version,
#: logged in DEV_LOG, never a silent restatement.
HEWB_VERSION = "1.0"

#: Annual cutoffs. Verified viable at scoping time: each carries 28-133 future
#: non-renewals, well above the stratified-CV floor. Finer than the V1 eval's
#: {2018, 2020, 2022, 2023} — annual resolution is what makes a lead-time
#: metric meaningful rather than a "sometime in the last two years" band.
ANNUAL_CUTOFFS: tuple[date, ...] = tuple(date(y, 1, 1) for y in range(2016, 2025))

#: Rank thresholds. A landmark is "flagged" at cutoff T for k if its rank in
#: the scored population at T is <= k. Reported for all three; never tuned to
#: the value that flatters a case (that is the tuning-until-it-wins the
#: baseline rule forbids). Note top-50 of ~5,900 is top ~0.85%, a strict bar.
K_VALUES: tuple[int, ...] = (10, 20, 50)


@dataclass(frozen=True)
class LandmarkCase:
    """One verified historical case in the benchmark.

    ``cas`` is the identity of record. It is cross-checked against the graph
    by ``verify_landmark_cas`` before any run, so this table is never trusted
    as typed — a mismatch fails loudly rather than silently benchmarking the
    wrong substance (the standing "never assert a CAS from memory" rule).
    """

    name: str
    cas: str
    note: str

    @property
    def substance_id(self) -> str:
        return f"substance:cas:{self.cas}"


#: The frozen HEWB 1.0 landmark set. Every CAS verified against graph node
#: labels at scoping time (2026-07-18); re-verified in code on every run.
#: Fluazinam is the anchor: a *negative* under the headline label (no EU
#: non-renewal) and a positive only under the early-warning variant. It is
#: kept precisely because that honesty is the point.
LANDMARK_CASES: tuple[LandmarkCase, ...] = (
    LandmarkCase("Clothianidin", "210880-92-5", "neonicotinoid, bee-toxicity ban"),
    LandmarkCase("Thiamethoxam", "153719-23-4", "neonicotinoid, bee-toxicity ban"),
    LandmarkCase("Imidacloprid", "138261-41-3", "neonicotinoid, bee-toxicity ban"),
    LandmarkCase("Chlorpyrifos", "2921-88-2", "developmental neurotoxicity"),
    LandmarkCase("Chlorpyrifos-methyl", "5598-13-0", "developmental neurotoxicity"),
    LandmarkCase("Thiacloprid", "111988-49-9", "reprotoxic"),
    LandmarkCase("Epoxiconazole", "133855-98-8", "CMR concern"),
    LandmarkCase("Mancozeb", "8018-01-7", "reprotoxic / endocrine"),
    LandmarkCase("Dimethoate", "60-51-5", "organophosphate"),
    LandmarkCase("Propikonazol", "60207-90-1", "triazole fungicide"),
    LandmarkCase("Fluazinam", "79622-59-6", "anchor case; SE reevaluation only"),
)

VARIANTS: tuple[tuple[str, frozenset[RegulatoryEventKind]], ...] = (
    ("headline", DEFAULT_POSITIVE_KINDS),
    ("early_warning", EARLY_WARNING_POSITIVE_KINDS),
)


def verify_landmark_cas(graph: TemporalGraph) -> None:
    """Fail loudly if any landmark CAS is absent or names a different label.

    Cheap insurance against the worst silent bug this benchmark could have:
    computing an impressive lead-time for the wrong substance because a CAS in
    ``LANDMARK_CASES`` was mistyped. Runs before every benchmark execution.
    """
    mismatches = []
    for case in LANDMARK_CASES:
        if not graph.has_node(case.substance_id):
            mismatches.append(f"{case.name} ({case.cas}): not in graph")
            continue
        label = graph.node(case.substance_id).label
        if label.lower() != case.name.lower():
            mismatches.append(f"{case.cas}: manifest says {case.name!r}, graph says {label!r}")
    if mismatches:
        raise ValueError("HEWB landmark CAS verification failed:\n  " + "\n  ".join(mismatches))


def action_date_for(
    substance_id: str,
    regevents: list[RegulatoryEvent],
    positive_kinds: frozenset[RegulatoryEventKind],
) -> date | None:
    """The earliest label-defining regulatory action for a substance.

    Earliest, not latest: a substance re-listed and re-actioned (mancozeb
    appears twice) is measured against the *first* time the label fired, which
    is what "early warning" is anchored to. ``None`` if the substance has no
    action under this label variant (e.g. fluazinam under the headline label).
    """
    dates = [
        e.event_date
        for e in regevents
        if e.substance_id == substance_id and e.kind in positive_kinds
    ]
    return min(dates) if dates else None


def rank_of(result: CutoffResult, target_id: str, model: str = "xgboost") -> int | None:
    """1-indexed rank of a substance in a cutoff's scored population.

    ``None`` when the substance is not in the population at this cutoff (no
    pre-cutoff dated fact, or already-realized and censored out by
    ``build_dataset``) — which is itself information, not a zero. Ties broken
    stably by original order, matching the reporting scripts.
    """
    if target_id not in result.ids:
        return None
    scores = result.scores[model]
    order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
    ranked_ids = [result.ids[i] for i in order]
    return ranked_ids.index(target_id) + 1


def _months_between(earlier: date, later: date) -> int:
    """Whole calendar months from ``earlier`` to ``later`` (may be 0)."""
    return (later.year - earlier.year) * 12 + (later.month - earlier.month)


@dataclass(frozen=True)
class CaseResult:
    """One landmark's benchmark outcome under one label variant.

    ``trajectory`` is the honest supporting evidence: (cutoff, rank,
    population) at every annual cutoff inside the case's measurable window
    ``[knowable, action]``. ``lead_times`` maps each k to (first_flagged
    cutoff, months of lead) — ``(None, None)`` means "never entered the top-k
    before the action landed", reported as such, never dropped.
    """

    name: str
    cas: str
    variant: str
    action_date: date | None
    trajectory: tuple[tuple[date, int | None, int], ...]
    lead_times: dict[int, tuple[date | None, int | None]]


def compute_case_result(
    case: LandmarkCase,
    variant: str,
    results: list[CutoffResult],
    regevents: list[RegulatoryEvent],
    positive_kinds: frozenset[RegulatoryEventKind],
    k_values: tuple[int, ...] = K_VALUES,
) -> CaseResult:
    """Lead-time and rank trajectory for one landmark under one variant.

    ``results`` are the per-cutoff outputs for this variant (ascending). The
    measurable window is ``[knowable, action]``: cutoffs after the action date
    are excluded (a flag at or after the action is not "early"), and cutoffs
    where the substance is not yet in the population contribute a ``None``
    rank. Lead time at k = months from the earliest cutoff where rank <= k to
    the action date.
    """
    action = action_date_for(case.substance_id, regevents, positive_kinds)
    trajectory: list[tuple[date, int | None, int]] = []
    if action is not None:
        for result in results:
            if result.cutoff > action:
                continue  # window upper bound: flags at/after the action aren't early
            trajectory.append(
                (result.cutoff, rank_of(result, case.substance_id), result.population)
            )

    lead_times: dict[int, tuple[date | None, int | None]] = {}
    for k in k_values:
        first_flagged = next(
            (cutoff for cutoff, rank, _ in trajectory if rank is not None and rank <= k),
            None,
        )
        if first_flagged is not None and action is not None:
            lead_times[k] = (first_flagged, _months_between(first_flagged, action))
        else:
            lead_times[k] = (None, None)

    return CaseResult(
        name=case.name,
        cas=case.cas,
        variant=variant,
        action_date=action,
        trajectory=tuple(trajectory),
        lead_times=lead_times,
    )


#: The V2b embedding-vs-tabular comparison this frozen row is sourced from.
#: Not re-run at HEWB's annual cutoffs: V2b's mechanism finding (only 29.2% of
#: the population has any walkable degrades_to/classified_as edge, so the
#: embedding is a constant zero vector for 71% of substances) is a property of
#: graph coverage, not cutoff granularity -- re-running at nine annual cutoffs
#: instead of four would not change *why* embeddings lose, only cost ~2x the
#: compute for no new conclusion. That is exactly the "squeezing another 0.01"
#: the scope's non-scope section warns against. See DEV_LOG's "V2b shipped"
#: entry for the original result and mechanism.
_V2B_EMBEDDING_MODELS = ("xgboost_tabular", "xgboost_embed_only", "xgboost_tabular_plus_embed")
_V2B_VARIANT_KEYS = {
    "headline": "headline (EU non-renewal only)",
    "early_warning": "early_warning (+ SE reevaluation)",
}


def embedding_comparison_rows(embed_eval_json: dict) -> list[dict]:
    """Reshape the raw V2b ``embed_eval_results.json`` into HEWB's frozen
    comparison rows: one row per (variant, cutoff, model), tagged so a reader
    can never mistake this for a fresh annual-cutoff run.

    Pure over its input (already-loaded JSON); the pipeline script does the
    file read. Silently returns ``[]`` for a variant/model missing from the
    input rather than raising -- a stale or partial V2b file should degrade
    the report, not crash the whole HEWB run.
    """
    rows: list[dict] = []
    for hewb_variant, v2b_key in _V2B_VARIANT_KEYS.items():
        payload = embed_eval_json.get(v2b_key)
        if not payload:
            continue
        for row in payload.get("full_population", []):
            if row["model"] not in _V2B_EMBEDDING_MODELS:
                continue
            rows.append(
                {
                    "variant": hewb_variant,
                    "cutoff": row["cutoff"],
                    "model": row["model"],
                    "population": row["population"],
                    "positives": row["positives"],
                    "average_precision": row["average_precision"],
                    "ap_ci_lo": row["ap_ci_lo"],
                    "ap_ci_hi": row["ap_ci_hi"],
                    "source": "frozen_v2b",
                }
            )
    return rows


@dataclass(frozen=True)
class HewbReport:
    """A full HEWB run: the aggregate ranking table plus every case result."""

    version: str
    aggregate: list[dict]  # summarize() rows, tagged with variant
    cases: list[CaseResult]
    embedding_comparison: list[dict] = field(default_factory=list)  # frozen V2b rows


def run_hewb(
    graph: TemporalGraph,
    sales: list[SalesRecord],
    regevents: list[RegulatoryEvent],
    seed: int = 42,
    v2b_embedding_json: dict | None = None,
) -> HewbReport:
    """Run HEWB end to end over both label variants.

    Verifies the landmark CAS set first (fails loudly on any mismatch), then
    for each variant runs the annual rolling-origin backtest once and derives
    both the aggregate table and every landmark's lead-time from those same
    per-cutoff results — no substance is scored twice.

    ``v2b_embedding_json``, if given, is the already-loaded contents of
    ``embed_eval_results.json`` (the pipeline script reads the file; this
    function stays pure). Reshaped via ``embedding_comparison_rows`` into
    ``HewbReport.embedding_comparison`` — the frozen graph-vs-tabular row the
    scope calls for, not a fresh embedding fit at annual cutoffs (see
    ``embedding_comparison_rows``'s docstring for why).
    """
    from hazium.ml.evaluate import summarize

    verify_landmark_cas(graph)

    aggregate: list[dict] = []
    cases: list[CaseResult] = []
    for variant, positive_kinds in VARIANTS:
        results = rolling_origin_eval(
            graph, sales, regevents, list(ANNUAL_CUTOFFS), seed=seed, positive_kinds=positive_kinds
        )
        for result in results:
            for row in summarize(result):
                aggregate.append({"variant": variant, **row})
        for case in LANDMARK_CASES:
            cases.append(compute_case_result(case, variant, results, regevents, positive_kinds))

    embedding_comparison = (
        embedding_comparison_rows(v2b_embedding_json) if v2b_embedding_json else []
    )

    return HewbReport(
        version=HEWB_VERSION,
        aggregate=aggregate,
        cases=cases,
        embedding_comparison=embedding_comparison,
    )
