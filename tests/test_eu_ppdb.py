"""EU PPDB adapter tests: real xlsx parsing for load_export, pure transforms
for regulatory_events_from.
"""

from datetime import date

import openpyxl

from hazium.models import RegulatoryEventKind
from hazium.sources.eu_ppdb import (
    _ASRow,
    _clean_cas,
    _parse_date,
    load_export,
    regulatory_events_from,
)

_HEADER = [
    "Active Substance ID",
    "Substance",
    "CAS Number",
    "Status under Reg. (EC) No 1107/2009",
    "Date of approval",
    "Expiration of approval",
    "Legislation",
]


def _write_export(tmp_path, rows: list[list]) -> str:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Pesticides Database - Active Substances (File created on 12/07/2026)"])
    ws.append([None])
    ws.append(_HEADER)
    for row in rows:
        ws.append(row)
    path = tmp_path / "export.xlsx"
    wb.save(path)
    return str(path)


class TestLoadExport:
    def test_finds_header_below_banner_and_parses(self, tmp_path) -> None:
        path = _write_export(
            tmp_path,
            [
                [
                    "32",
                    "Fluazinam",
                    "79622-59-6",
                    "Approved",
                    "01/03/2009",
                    "30/11/2027",
                    "Dir. 2008/108",
                ]
            ],
        )
        rows = load_export(path)
        assert len(rows) == 1
        r = rows[0]
        assert r.as_id == "32"
        assert r.name == "Fluazinam"
        assert r.cas_number == "79622-59-6"
        assert r.status == "Approved"
        assert r.approval_date == date(2009, 3, 1)
        assert r.expiry_date == date(2027, 11, 30)

    def test_no_cas_allocated_becomes_none(self, tmp_path) -> None:
        path = _write_export(
            tmp_path,
            [
                [
                    "351",
                    "Some pheromone",
                    "No CAS allocated",
                    "Not approved",
                    None,
                    None,
                    "2004/129/EC",
                ]
            ],
        )
        assert load_export(path)[0].cas_number is None

    def test_legislation_ref_in_date_cell_yields_none(self, tmp_path) -> None:
        # pending substances sometimes carry a legislation ref where a date goes
        path = _write_export(
            tmp_path,
            [
                [
                    "1062",
                    "(3E)-dec-3-en-2-one",
                    "10519-33-2",
                    "Pending",
                    "Reg. (EU) 2016/138",
                    None,
                    "x",
                ]
            ],
        )
        assert load_export(path)[0].approval_date is None

    def test_blank_id_rows_skipped(self, tmp_path) -> None:
        path = _write_export(
            tmp_path,
            [
                ["32", "Fluazinam", "79622-59-6", "Approved", "01/03/2009", "30/11/2027", "x"],
                [None, None, None, None, None, None, None],
            ],
        )
        assert len(load_export(path)) == 1


class TestCleanCas:
    def test_no_cas_allocated(self) -> None:
        assert _clean_cas("No CAS allocated") is None

    def test_none(self) -> None:
        assert _clean_cas(None) is None

    def test_real(self) -> None:
        assert _clean_cas("79622-59-6") == "79622-59-6"


class TestParseDate:
    def test_ddmmyyyy(self) -> None:
        assert _parse_date("31/08/2023") == date(2023, 8, 31)

    def test_datetime_passthrough(self) -> None:
        from datetime import datetime

        assert _parse_date(datetime(2023, 8, 31)) == date(2023, 8, 31)

    def test_legislation_ref_is_none(self) -> None:
        assert _parse_date("Reg. (EU) 2016/138") is None

    def test_none(self) -> None:
        assert _parse_date(None) is None


def _row(**overrides) -> _ASRow:
    base = dict(
        as_id="32",
        name="Fluazinam",
        cas_number="79622-59-6",
        status="Approved",
        approval_date=date(2009, 3, 1),
        expiry_date=date(2027, 11, 30),
    )
    base.update(overrides)
    return _ASRow(**base)


class TestRegulatoryEventsFrom:
    def test_approved_substance_yields_approval_event(self) -> None:
        events = regulatory_events_from([_row()])
        assert len(events) == 1
        e = events[0]
        assert e.kind == RegulatoryEventKind.APPROVAL
        assert e.event_date == date(2009, 3, 1)
        assert e.substance_id == "substance:cas:79622-59-6"
        assert e.jurisdiction == "EU"
        assert e.known_at == e.event_date

    def test_non_renewed_substance_yields_approval_and_non_renewal(self) -> None:
        row = _row(
            status="Not approved", approval_date=date(2009, 9, 1), expiry_date=date(2023, 8, 31)
        )
        events = {e.kind: e for e in regulatory_events_from([row])}
        assert RegulatoryEventKind.APPROVAL in events
        assert RegulatoryEventKind.NON_RENEWAL in events
        assert events[RegulatoryEventKind.NON_RENEWAL].event_date == date(2023, 8, 31)

    def test_never_approved_substance_yields_nothing(self) -> None:
        # non-inclusion wave: status Not approved, no approval/expiry dates
        row = _row(status="Not approved", approval_date=None, expiry_date=None)
        assert regulatory_events_from([row]) == []

    def test_approved_without_expiry_yields_only_approval(self) -> None:
        row = _row(status="Approved", expiry_date=None)
        events = regulatory_events_from([row])
        assert [e.kind for e in events] == [RegulatoryEventKind.APPROVAL]

    def test_not_approved_with_expiry_but_no_approval_date_still_non_renewal(self) -> None:
        row = _row(status="Not approved", approval_date=None, expiry_date=date(2020, 1, 1))
        assert [e.kind for e in regulatory_events_from([row])] == [RegulatoryEventKind.NON_RENEWAL]

    def test_no_cas_falls_back_to_name_id(self) -> None:
        row = _row(cas_number=None, name="Some pheromone blend")
        assert (
            regulatory_events_from([row])[0].substance_id == "substance:name:some-pheromone-blend"
        )
