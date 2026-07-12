"""CLP adapter tests: real xlsx parsing for load(), pure transforms for
classifications_from().
"""

from datetime import date

import openpyxl

from hazium.sources.clp import (
    _HistoryRow,
    _clean_cas,
    _parse_date,
    _split,
    classifications_from,
    load,
)

_HEADER = [
    "Index No",
    "ATP",
    "CELEX",
    "Chemical Name",
    "EC No",
    "CAS No",
    "Hazard Class and Category Code(s)",
    "Classification Hazard Statement Code(s)",
    "Labelling Pictogram, Signal Word Code(s)",
    "Labelling Hazard Statement Code(s)",
    "Labelling Suppl. Hazard Statement Code(s)",
    "M, SCL, ATE",
    "Notes",
    "Comment",
    "In application",
    "EUR-Lex Link",
]


def _write_workbook(tmp_path, rows: list[list]) -> str:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    sheet = wb.create_sheet("History")
    sheet.append(_HEADER)
    for row in rows:
        sheet.append(row)
    path = tmp_path / "annex_vi.xlsx"
    wb.save(path)
    return str(path)


def _fluazinam_row() -> list:
    return [
        "612-287-00-5",
        "ATP06",
        "32014R0605",
        "fluazinam (ISO)",
        "-",
        "79622-59-6",
        "Repr. 2\nAquatic Chronic 1",
        "H361d\nH410",
        "GHS08\nGHS09\nDgr",
        "H361d\nH410",
        "",
        "M = 10",
        "",
        "",
        date(2015, 4, 1),
        "https://eur-lex.europa.eu/...",
    ]


class TestLoad:
    def test_parses_fluazinam_row(self, tmp_path) -> None:
        path = _write_workbook(tmp_path, [_fluazinam_row()])
        rows = load(path)
        assert len(rows) == 1
        row = rows[0]
        assert row.index_no == "612-287-00-5"
        assert row.atp == "ATP06"
        assert row.celex == "32014R0605"
        assert row.cas_number == "79622-59-6"
        assert row.hazard_classes == ("Repr. 2", "Aquatic Chronic 1")
        assert row.hazard_codes == ("H361d", "H410")
        assert row.known_at == date(2015, 4, 1)

    def test_row_missing_hazard_codes_is_dropped(self, tmp_path) -> None:
        row = _fluazinam_row()
        row[7] = ""  # Classification Hazard Statement Code(s)
        path = _write_workbook(tmp_path, [row])
        assert load(path) == []

    def test_row_missing_application_date_is_dropped(self, tmp_path) -> None:
        row = _fluazinam_row()
        row[14] = None  # In application
        path = _write_workbook(tmp_path, [row])
        assert load(path) == []

    def test_row_missing_name_is_dropped(self, tmp_path) -> None:
        row = _fluazinam_row()
        row[3] = None  # Chemical Name
        path = _write_workbook(tmp_path, [row])
        assert load(path) == []

    def test_group_entry_dash_cas_becomes_none(self, tmp_path) -> None:
        row = _fluazinam_row()
        row[5] = "-"  # CAS No
        path = _write_workbook(tmp_path, [row])
        assert load(path)[0].cas_number is None


class TestSplit:
    def test_splits_newline_separated_values(self) -> None:
        assert _split("H361d\nH410") == ("H361d", "H410")

    def test_none_and_empty_yield_empty_tuple(self) -> None:
        assert _split(None) == ()
        assert _split("") == ()

    def test_blank_lines_dropped(self) -> None:
        assert _split("H361d\n\nH410") == ("H361d", "H410")


class TestCleanCas:
    def test_dash_is_none(self) -> None:
        assert _clean_cas("-") is None

    def test_none_is_none(self) -> None:
        assert _clean_cas(None) is None

    def test_real_cas_passed_through(self) -> None:
        assert _clean_cas("79622-59-6") == "79622-59-6"


class TestParseDate:
    def test_date_object_passthrough(self) -> None:
        assert _parse_date(date(2015, 4, 1)) == date(2015, 4, 1)

    def test_non_date_yields_none(self) -> None:
        assert _parse_date("not a date") is None
        assert _parse_date(None) is None


def _row(**overrides) -> _HistoryRow:
    base = dict(
        index_no="612-287-00-5",
        atp="ATP06",
        celex="32014R0605",
        name="fluazinam (ISO)",
        cas_number="79622-59-6",
        hazard_classes=("Repr. 2", "Aquatic Chronic 1"),
        hazard_codes=("H361d", "H410"),
        known_at=date(2015, 4, 1),
    )
    base.update(overrides)
    return _HistoryRow(**base)


class TestClassificationsFrom:
    def test_one_classification_per_hazard_code(self) -> None:
        classifications = classifications_from([_row()])
        assert len(classifications) == 2
        codes = {c.hazard_code for c in classifications}
        assert codes == {"H361d", "H410"}

    def test_cas_resolved_substance_id(self) -> None:
        classifications = classifications_from([_row()])
        assert all(c.substance_id == "substance:cas:79622-59-6" for c in classifications)

    def test_hazard_class_paired_positionally(self) -> None:
        classifications = {c.hazard_code: c for c in classifications_from([_row()])}
        assert classifications["H361d"].hazard_class == "Repr. 2"
        assert classifications["H410"].hazard_class == "Aquatic Chronic 1"

    def test_mismatched_lengths_drop_pairing_rather_than_guess(self) -> None:
        row = _row(hazard_classes=("Repr. 2",), hazard_codes=("H361d", "H410", "H400"))
        classifications = classifications_from([row])
        assert all(c.hazard_class is None for c in classifications)

    def test_atp_and_celex_carried_through(self) -> None:
        classification = classifications_from([_row()])[0]
        assert classification.atp == "ATP06"
        assert classification.celex == "32014R0605"

    def test_known_at_is_in_application_date(self) -> None:
        classification = classifications_from([_row()])[0]
        assert classification.known_at == date(2015, 4, 1)

    def test_no_cas_falls_back_to_name_based_id(self) -> None:
        row = _row(cas_number=None, name="Some group entry")
        classification = classifications_from([row])[0]
        assert classification.substance_id == "substance:name:some-group-entry"

    def test_source_is_echa_clp_annex_vi(self) -> None:
        assert classifications_from([_row()])[0].source == "echa:clp-annex-vi"
