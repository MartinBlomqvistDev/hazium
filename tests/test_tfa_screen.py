"""Tests for the TFA-precursor screen and the structure records behind it.

These fix the rule, not the outcome. How many substances the screen flags is
allowed to move when PubChem or the approved population moves; `pipeline/35` is
what reports that. What must not move is the arithmetic, the treatment of an
unresolved structure, or the refusal to count a chance baseline as a hit.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from hazium.screen.tfa import KEMI_TFA_COHORT, screen
from hazium.sources.pubchem_structure import CF3_PATTERNS, StructureRecord

FLUAZINAM = "substance:cas:79622-59-6"


def rec(sid: str, formula: str | None, smiles: str | None, resolved: bool = True):
    return StructureRecord(
        substance_id=sid,
        cas=sid.removeprefix("substance:cas:"),
        molecular_formula=formula,
        smiles=smiles,
        resolved=resolved,
    )


# --- structure parsing ------------------------------------------------------


def test_fluorine_count_reads_hill_notation():
    assert rec("s:1", "C13H4Cl2F6N4O4", None).fluorine_count == 6
    assert rec("s:2", "C9H6F3N3O", None).fluorine_count == 3


def test_a_single_fluorine_has_no_digit():
    assert rec("s:1", "C7H5FO2", None).fluorine_count == 1


def test_iron_is_not_fluorine():
    """Hill notation puts Fe next to F; a naive regex reads it as fluorine."""
    assert rec("s:1", "C10H12FeN2O8", None).fluorine_count == 0


def test_no_formula_means_no_fluorine():
    assert rec("s:1", None, None).fluorine_count == 0


@pytest.mark.parametrize("pattern", CF3_PATTERNS)
def test_every_declared_cf3_spelling_is_detected(pattern):
    assert rec("s:1", "C2F3", f"CC{pattern}").has_cf3


def test_two_cf3_groups_are_counted():
    assert rec("s:1", "C13H4Cl2F6N4O4", "C(F)(F)FC1=CC=CC=C1C(F)(F)F").cf3_groups == 2


def test_fluorine_without_cf3_is_flagged_for_review():
    """A pattern miss and a genuinely non-CF3 molecule look identical here."""
    assert rec("s:1", "C6H3F3", "FC1=CC(F)=CC(F)=C1").unexplained_fluorine


def test_two_fluorines_without_cf3_is_not_worth_flagging():
    assert not rec("s:1", "C6H4F2", "FC1=CC=C(F)C=C1").unexplained_fluorine


# --- the screen -------------------------------------------------------------


def test_only_cf3_carriers_are_flagged():
    structures = {
        "a": rec("a", "C9H6F3N3O", "CC(F)(F)F"),
        "b": rec("b", "C6H6", "CC1=CC=CC=C1"),
    }
    result = screen(structures, {"a": "Alpha", "b": "Beta"})
    assert [e.substance_id for e in result.flagged] == ["a"]
    assert result.population == 2


def test_unresolved_structures_are_excluded_not_assumed_clean():
    structures = {
        "a": rec("a", "C9H6F3N3O", "CC(F)(F)F"),
        "b": rec("b", None, None, resolved=False),
    }
    result = screen(structures, {})
    assert result.population == 1, "an unresolved structure is not a population member"
    assert result.unresolved == 1


def test_exposure_is_capped_so_the_largest_seller_cannot_own_the_ranking():
    structures = {
        "big": rec("big", "CF3", "CC(F)(F)F"),
        "huge": rec("huge", "CF3", "CC(F)(F)F"),
    }
    result = screen(structures, {}, tonnes={"big": 50.0, "huge": 800.0})
    scores = {e.substance_id: e.score for e in result.flagged}
    assert scores["big"] == scores["huge"]


def test_a_sold_precursor_outranks_a_heavier_one_nobody_buys():
    """Payload and exposure each top out at 1.0, so exposure can overturn payload.

    That is the intended reading of the rule: a substance with half the fluorine
    payload but real Swedish tonnage is a bigger groundwater problem than a
    heavier one with no recorded sales.
    """
    structures = {
        "two": rec("two", "CF6", "C(F)(F)FC(F)(F)F"),
        "one": rec("one", "CF3", "CC(F)(F)F"),
    }
    result = screen(structures, {}, tonnes={"one": 50.0})
    scores = {e.substance_id: e.score for e in result.flagged}
    assert scores["one"] == 1.5, "one CF3 (0.5) at full exposure (1.0)"
    assert scores["two"] == 1.0, "two CF3 (1.0) with no recorded sales"
    assert [e.substance_id for e in result.flagged] == ["one", "two"]


def test_cohort_membership_is_marked_not_scored():
    """Being on KEMI's list must not change a substance's position."""
    structures = {
        FLUAZINAM: rec(FLUAZINAM, "C13H4Cl2F6N4O4", "C(F)(F)FC(F)(F)F"),
        "other": rec("other", "C13H4Cl2F6N4O4", "C(F)(F)FC(F)(F)F"),
    }
    result = screen(structures, {FLUAZINAM: "Fluazinam", "other": "Other"})
    by_id = {e.substance_id: e for e in result.flagged}
    assert by_id[FLUAZINAM].in_kemi_cohort
    assert not by_id["other"].in_kemi_cohort
    assert by_id[FLUAZINAM].score == by_id["other"].score


def test_chance_baseline_scales_with_how_much_is_flagged():
    structures = {f"s{i}": rec(f"s{i}", "C6H6", "CC1=CC=CC=C1") for i in range(60)}
    structures["s0"] = rec("s0", "CF3", "CC(F)(F)F")
    result = screen(structures, {})
    # One flagged of 60, six cohort members: 6 * 1/60 expected by chance.
    assert result.expected_kemi_by_chance == pytest.approx(0.1)


def test_chance_baseline_is_zero_for_an_empty_population():
    assert screen({}, {}).expected_kemi_by_chance == 0.0


def test_the_cohort_constant_is_the_six_kemi_named():
    assert len(KEMI_TFA_COHORT) == 6
    assert FLUAZINAM in KEMI_TFA_COHORT


def test_result_is_frozen():
    result = screen({}, {})
    with pytest.raises(ValidationError):
        result.population = 5
