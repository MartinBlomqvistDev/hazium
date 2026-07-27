"""Tests for the discrete-time survival panel.

The panel is the whole contribution here, so the tests are about its shape
rather than about model scores: who is at risk, when the outcome fires, and
that a substance leaves the risk set once it has been withdrawn. Getting any of
those wrong would quietly reintroduce the mixing of *whether* with *when* that
this framing exists to separate.
"""

from datetime import date

import pandas as pd
import pytest
from pydantic import ValidationError

from hazium.benchmark.survival import (
    AGE_FEATURES,
    EVENT,
    EVIDENCE_FEATURES,
    EVIDENCE_GROUPS,
    IN_FUNNEL_GROUPS,
    SUBJECT,
    YEAR,
    PanelSpec,
    baseline_hazard,
    feature_columns,
    first_event_dates,
    forward_split,
)
from hazium.models import RegulatoryEvent, RegulatoryEventKind


def _event(sid: str, when: date, kind=RegulatoryEventKind.NON_RENEWAL) -> RegulatoryEvent:
    return RegulatoryEvent(
        source="test",
        known_at=when,
        substance_id=sid,
        kind=kind,
        jurisdiction="EU",
        event_date=when,
    )


def test_first_event_takes_the_earliest_not_the_latest() -> None:
    """A withdrawal can carry several records; lead time anchors to the first."""
    events = [
        _event("substance:cas:1", date(2020, 5, 1)),
        _event("substance:cas:1", date(2018, 3, 1)),
        _event("substance:cas:1", date(2021, 1, 1)),
    ]
    assert first_event_dates(events, RegulatoryEventKind.NON_RENEWAL) == {
        "substance:cas:1": date(2018, 3, 1)
    }


def test_first_event_ignores_other_event_kinds() -> None:
    events = [
        _event("substance:cas:1", date(2015, 1, 1), RegulatoryEventKind.APPROVAL),
        _event("substance:cas:1", date(2020, 1, 1), RegulatoryEventKind.NON_RENEWAL),
    ]
    assert first_event_dates(events, RegulatoryEventKind.NON_RENEWAL) == {
        "substance:cas:1": date(2020, 1, 1)
    }


def test_feature_columns_keeps_age_and_evidence_separable() -> None:
    """Every arm of the comparison is assembled from this, so it must be exact."""
    assert feature_columns(age=True, evidence=False) == list(AGE_FEATURES)
    assert feature_columns(age=False, evidence=True) == list(EVIDENCE_FEATURES)
    both = feature_columns()
    assert both[: len(AGE_FEATURES)] == list(AGE_FEATURES)
    assert len(both) == len(AGE_FEATURES) + len(EVIDENCE_FEATURES)


def test_feature_columns_can_select_named_groups() -> None:
    cols = feature_columns(age=True, groups=("efsa",))
    assert cols == list(AGE_FEATURES) + list(EVIDENCE_GROUPS["efsa"])


def test_no_age_feature_leaks_into_the_evidence_set() -> None:
    """If an age column appeared in a group, the arms would stop being separable."""
    assert not set(AGE_FEATURES) & set(EVIDENCE_FEATURES)


def test_in_funnel_groups_are_real_groups() -> None:
    assert set(EVIDENCE_GROUPS) >= IN_FUNNEL_GROUPS


def test_forward_split_never_trains_on_the_future() -> None:
    panel = pd.DataFrame({YEAR: [2015, 2016, 2017, 2018], EVENT: [0, 1, 0, 1]})
    train, test = forward_split(panel, 2016)
    assert panel[YEAR][train].max() == 2016
    assert panel[YEAR][test].min() == 2017
    assert not (train & test).any()
    assert (train | test).all()


def test_baseline_hazard_rises_with_approval_age() -> None:
    panel = pd.DataFrame(
        {
            "eu_years_since_first_approval": [1, 2, 3, 12, 13, 14],
            EVENT: [0, 0, 0, 1, 1, 0],
        }
    )
    out = baseline_hazard(panel, edges=(0, 5, 20))
    young = out[out["age_from"] == 0].iloc[0]
    old = out[out["age_from"] == 5].iloc[0]
    assert young["hazard"] == 0.0
    assert old["hazard"] == pytest.approx(2 / 3)


def test_panel_spec_is_frozen_and_rejects_unknown_fields() -> None:
    spec = PanelSpec()
    with pytest.raises(ValidationError):
        spec.horizon_years = 5
    with pytest.raises(ValidationError):
        PanelSpec(horizen_years=2)


def test_panel_spec_defaults_match_the_reported_configuration() -> None:
    spec = PanelSpec()
    assert (spec.first_year, spec.last_year, spec.horizon_years) == (2009, 2024, 1)
    assert spec.positive_kind is RegulatoryEventKind.NON_RENEWAL


def test_panel_column_names_do_not_collide_with_features() -> None:
    """The bookkeeping columns are joined onto the feature frame, so they must
    not shadow a real feature name."""
    for column in (SUBJECT, YEAR, EVENT):
        assert column.startswith("_")
        assert column not in set(AGE_FEATURES) | set(EVIDENCE_FEATURES)
