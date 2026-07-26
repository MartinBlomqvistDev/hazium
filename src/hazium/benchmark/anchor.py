"""Where a named cohort lands in a ranking, and whether that beats chance.

Hazium exists because of fluazinam, so "does the model rank fluazinam highly"
is the question a reader asks first. Asked of one substance it is unanswerable:
any ranking puts some substance at some position, and a single favourable
position proves nothing. Asked of the whole cohort a regulator actually named,
it becomes a measurement.

Kemikalieinspektionen opened a reevaluation of six TFA-forming plant protection
substances on 2025-11-20. That is an independent, dated, externally-defined set,
chosen by a regulator rather than by this project, which is what makes it usable
as a test rather than as an anecdote. If the evidence carried a groundwater
signal, those six should sit high. This module reports where they sit.

The comparison is against chance, not against zero. A cohort of six drawn at
random from a ranking of 260 lands at a median around the midpoint, and about
2.3 of them fall in any top 100. Anything at or below those numbers is a miss,
however good one member of the cohort happens to look on its own.
"""

from __future__ import annotations

from statistics import median

from pydantic import BaseModel, ConfigDict


class CohortResult(BaseModel):
    """Where a named cohort sits in a ranking, against what chance would give."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    population: int
    """How many substances the ranking covers."""

    ranks: dict[str, int]
    """Rank per cohort member, 1 being the most concerning."""

    missing: tuple[str, ...] = ()
    """Cohort members absent from the ranking entirely."""

    top_k: int
    """The published band the hit count is measured against."""

    hits_in_top_k: int
    """Cohort members inside that band."""

    expected_in_top_k: float
    """How many would fall there by chance."""

    median_rank: float
    """Median rank of the members present."""

    median_percentile: float
    """That median as a share of the population; 0.5 is chance."""

    @property
    def beats_chance(self) -> bool:
        """True only if the cohort sits higher than a random draw would.

        Both conditions have to hold. A cohort can land one member in the top
        band by luck while the rest sit at the bottom, and that is a miss, not
        a detection.
        """
        return self.hits_in_top_k > self.expected_in_top_k and self.median_percentile < 0.5


def cohort_ranks(ranked_ids: list[str], cohort: list[str], *, top_k: int = 100) -> CohortResult:
    """Locate a cohort inside a ranking.

    Args:
        ranked_ids: Substance ids, most concerning first, no duplicates.
        cohort: The substance ids to locate.
        top_k: The published band to count hits in.

    Returns:
        A `CohortResult`. Members absent from the ranking are reported in
        ``missing`` and excluded from the median rather than imputed to the
        bottom, because absence from the at-risk set is a different fact from
        a low rank.

    Raises:
        ValueError: If ``ranked_ids`` contains duplicates, which would make
            every rank ambiguous.
    """
    if len(set(ranked_ids)) != len(ranked_ids):
        raise ValueError("ranked_ids contains duplicates; ranks would be ambiguous")

    position = {sid: i for i, sid in enumerate(ranked_ids, start=1)}
    wanted = list(dict.fromkeys(cohort))
    ranks = {sid: position[sid] for sid in wanted if sid in position}
    missing = tuple(sid for sid in wanted if sid not in position)

    population = len(ranked_ids)
    values = sorted(ranks.values())
    med = float(median(values)) if values else float("nan")
    band = min(top_k, population)
    return CohortResult(
        population=population,
        ranks=ranks,
        missing=missing,
        top_k=band,
        hits_in_top_k=sum(1 for r in values if r <= band),
        expected_in_top_k=len(values) * band / population if population else 0.0,
        median_rank=med,
        median_percentile=med / population if values and population else float("nan"),
    )
