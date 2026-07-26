"""Which approved pesticides can become TFA, and which of those matter most.

HEWB predicts EU non-renewal, which is a committee decision. The hazard that
started this project is not a committee decision: fluazinam degrades into
trifluoroacetic acid, a persistent PFAS that reaches groundwater, and no
regulatory record of the parent substance mentions it. Measured against the six
substances Kemikalieinspektionen opened for reevaluation on 2025-11-20, HEWB
ranks them slightly worse than chance. It was asking the wrong question.

This asks the right one, and it needs no model. TFA comes from trifluoromethyl
groups, so the population that can form it is the population that carries one.
That is a fact about the molecule, available from PubChem, identical at every
cutoff and impossible to leak.

**Screening, not prediction.** A CF3 group means a substance *can* yield TFA,
not that it does, and certainly not that it will be restricted. Whether a given
CF3 group survives to become TFA depends on where it sits in the molecule and on
degradation pathways this module does not model. The screen is deliberately
over-inclusive: it is meant to bound the problem, and a bound that misses real
cases is worthless while a bound that includes some innocents is merely wide.

**Why the weights are written down rather than fitted.** Six confirmed
substances cannot train anything. Fitting weights on them and then reporting how
well those weights rank them would be measuring nothing. So exposure and
fluorine payload are combined by a stated rule, the rule is in this file where
anyone can disagree with it, and the six are held out as a check on the
resulting order rather than used to produce it.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from hazium.sources.pubchem_structure import StructureRecord

#: Kemikalieinspektionen, 2025-11-20: plant protection products that can form
#: TFA, opened for reevaluation with a decision due by April 2028. Held out as a
#: check on the screen, never used to build it. This is the only list in this
#: module that a regulator wrote.
KEMI_TFA_COHORT: dict[str, str] = {
    "substance:cas:79622-59-6": "Fluazinam",
    "substance:cas:158062-67-0": "Flonicamid",
    "substance:cas:83164-33-4": "Diflufenican",
    "substance:cas:658066-35-4": "Fluopyram",
    "substance:cas:1417782-03-6": "Mefentrifluconazole",
    "substance:cas:102851-06-9": "tau-fluvalinate",
}

#: Substances EFSA's own degradation records already link to TFA, independently
#: of KEMI and of this screen. A second, differently-sourced check: anything
#: here that the structural rule fails to flag is a hole in the rule.
EFSA_CONFIRMED_TFA_PARENTS: frozenset[str] = frozenset(
    {
        "substance:cas:142459-58-3",  # flufenacet
        "substance:cas:96525-23-4",  # flurtamone
        "substance:cas:66332-96-5",  # flutolanil
    }
)

#: Weight on fluorine payload against Swedish sales volume. Set to 1.0, meaning
#: the two count equally after each is put on a 0-1 scale. There is no evidence
#: for a different number and inventing one would dress a judgement up as a
#: measurement.
PAYLOAD_WEIGHT = 1.0

#: Tonnage above which a substance counts as fully exposed. Swedish plant
#: protection sales are extremely skewed, with a median around 0.2 tonnes and a
#: maximum near 800, so exposure is capped rather than scaled linearly: past a
#: point, more tonnes do not mean proportionally more groundwater risk, and
#: without a cap the largest seller would decide the whole ranking.
EXPOSURE_CAP_TONNES = 50.0


class ScreenEntry(BaseModel):
    """One substance's position in the TFA-precursor screen."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    substance_id: str
    name: str
    molecular_formula: str | None
    fluorine_count: int
    cf3_groups: int
    tonnes: float | None = Field(default=None, description="Swedish sales, latest year")
    crops: tuple[str, ...] = ()
    score: float = Field(description="Payload and exposure combined by the stated rule")
    in_kemi_cohort: bool = False
    efsa_confirmed: bool = False


class ScreenResult(BaseModel):
    """The screen, and how it did against the two held-out confirmations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    population: int = Field(description="Approved substances with a resolved structure")
    unresolved: int = Field(description="Approved substances PubChem could not match")
    flagged: tuple[ScreenEntry, ...]
    unexplained_fluorine: tuple[str, ...] = Field(
        default=(),
        description="Three or more fluorines but no CF3 matched; a possible pattern miss",
    )

    @property
    def flagged_count(self) -> int:
        return len(self.flagged)

    @property
    def kemi_found(self) -> int:
        return sum(1 for e in self.flagged if e.in_kemi_cohort)

    @property
    def kemi_total(self) -> int:
        return len(KEMI_TFA_COHORT)

    @property
    def efsa_found(self) -> int:
        return sum(1 for e in self.flagged if e.efsa_confirmed)

    @property
    def expected_kemi_by_chance(self) -> float:
        """How many of the cohort a same-sized random draw would catch."""
        if not self.population:
            return 0.0
        return self.kemi_total * self.flagged_count / self.population


def _exposure(tonnes: float | None) -> float:
    if not tonnes or tonnes <= 0:
        return 0.0
    return min(tonnes, EXPOSURE_CAP_TONNES) / EXPOSURE_CAP_TONNES


def _payload(structure: StructureRecord) -> float:
    """Fluorine payload on a 0-1 scale.

    Driven by CF3 count rather than total fluorine, because a fluorine bonded
    somewhere else in the molecule is not a TFA precursor. Two CF3 groups is
    treated as the practical ceiling; nothing in the approved population carries
    more than that.
    """
    return min(structure.cf3_groups, 2) / 2


def screen(
    structures: dict[str, StructureRecord],
    names: dict[str, str],
    tonnes: dict[str, float] | None = None,
    crops: dict[str, list[str]] | None = None,
) -> ScreenResult:
    """Flag every approved substance that can form TFA, and rank the flagged.

    Args:
        structures: Structure records by substance id, for the approved
            population being screened.
        names: Display names by substance id.
        tonnes: Latest Swedish sales tonnage by substance id, where known.
        crops: Approved Swedish crop uses by substance id, where known.

    Returns:
        A `ScreenResult`. Substances PubChem could not resolve are counted in
        ``unresolved`` and excluded from the population rather than assumed
        fluorine-free, because an unresolved structure is missing evidence, not
        evidence of absence.
    """
    tonnes = tonnes or {}
    crops = crops or {}

    resolved = {sid: s for sid, s in structures.items() if s.resolved}
    unresolved = tuple(sid for sid, s in structures.items() if not s.resolved)

    entries: list[ScreenEntry] = []
    for sid, structure in resolved.items():
        if not structure.has_cf3:
            continue
        volume = tonnes.get(sid)
        score = PAYLOAD_WEIGHT * _payload(structure) + _exposure(volume)
        entries.append(
            ScreenEntry(
                substance_id=sid,
                name=names.get(sid, sid),
                molecular_formula=structure.molecular_formula,
                fluorine_count=structure.fluorine_count,
                cf3_groups=structure.cf3_groups,
                tonnes=volume,
                crops=tuple(crops.get(sid, ())),
                score=round(score, 4),
                in_kemi_cohort=sid in KEMI_TFA_COHORT,
                efsa_confirmed=sid in EFSA_CONFIRMED_TFA_PARENTS,
            )
        )

    entries.sort(key=lambda e: (-e.score, e.name))
    return ScreenResult(
        population=len(resolved),
        unresolved=len(unresolved),
        flagged=tuple(entries),
        unexplained_fluorine=tuple(sid for sid, s in resolved.items() if s.unexplained_fluorine),
    )
