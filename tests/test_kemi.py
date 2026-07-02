"""KEMI sales report adapter: cell semantics, row reconstruction, real PDF.

The unit tests exercise the word-geometry parser on synthetic pdfplumber
words. The integration test runs only if the real 2024 report has been
downloaded (pipeline/01_ingest_kemi_sales.py puts it in data/raw/kemi/).
"""

from datetime import date
from pathlib import Path

import pytest

from hazium.sources.kemi import (
    _creation_date,
    _parse_page_words,
    _parse_quantity,
    parse_sales_report,
    report_url,
)

REPORT_2024 = Path(__file__).parent.parent / "data" / "raw" / "kemi" / "forsalda_bkm_2024.pdf"


def _word(text: str, x0: float, top: float) -> dict:
    return {"text": text, "x0": x0, "x1": x0 + 5 * len(text), "top": top}


class TestCellSemantics:
    def test_dash_asserts_zero_sales(self) -> None:
        assert _parse_quantity("-") == 0.0

    def test_confidential_asserts_nothing(self) -> None:
        assert _parse_quantity("*)") is None

    def test_decimal_comma(self) -> None:
        assert _parse_quantity("12,1") == 12.1

    def test_bare_integer(self) -> None:
        assert _parse_quantity("8") == 8.0


class TestRowReconstruction:
    HEADER = [_word("2023", 200, 10), _word("2024", 260, 10)]

    def test_values_map_to_nearest_year_column(self) -> None:
        words = [
            *self.HEADER,
            _word("Fluazinam", 30, 50),
            _word("4,8", 205, 50),
            _word("12,1", 262, 50),
        ]
        assert _parse_page_words(words) == [("Fluazinam", {2023: "4,8", 2024: "12,1"})]

    def test_blank_cells_produce_no_entry(self) -> None:
        words = [*self.HEADER, _word("Fenpicoxamid", 30, 50), _word("*)", 262, 50)]
        assert _parse_page_words(words) == [("Fenpicoxamid", {2024: "*)"})]

    def test_wrapped_name_attaches_to_nearest_value_row(self) -> None:
        words = [
            *self.HEADER,
            _word("Aktivt", 30, 46),
            _word("klor", 85, 46),
            _word("frisatt", 125, 46),
            _word("-", 205, 50),
            _word("6,6", 262, 50),
            _word("från", 30, 54),
            _word("natriumhypoklorit", 70, 54),
            _word("Glyfosat", 30, 70),
            _word("714,2", 200, 70),
            _word("751,2", 260, 70),
        ]
        assert _parse_page_words(words) == [
            ("Aktivt klor frisatt från natriumhypoklorit", {2023: "-", 2024: "6,6"}),
            ("Glyfosat", {2023: "714,2", 2024: "751,2"}),
        ]

    def test_page_without_year_header_yields_nothing(self) -> None:
        assert _parse_page_words([_word("Innehåll", 30, 10)]) == []


def test_creation_date_parses_pdf_timestamp() -> None:
    assert _creation_date({"CreationDate": "D:20250616090351+02'00'"}) == date(2025, 6, 16)


def test_creation_date_missing_fails_loudly() -> None:
    with pytest.raises(ValueError):
        _creation_date({})


def test_report_url_pattern() -> None:
    assert report_url(2024).endswith("forsalda_bkm_2024.pdf")


@pytest.mark.skipif(not REPORT_2024.exists(), reason="2024 report not downloaded")
class TestRealReport:
    def test_fluazinam_series_matches_published_figures(self) -> None:
        records = parse_sales_report(REPORT_2024)
        fluazinam = {
            r.year: r.tonnes_active_substance
            for r in records
            if r.substance_id == "substance:name:fluazinam"
        }
        assert fluazinam[2020] == 1.2
        assert fluazinam[2024] == 12.1

    def test_provenance_and_scale(self) -> None:
        records = parse_sales_report(REPORT_2024)
        assert len(records) > 1500  # ~280 substances x 8 years, minus blanks
        assert all(r.source == "kemi:forsalda:2024" for r in records)
        assert all(r.known_at == date(2025, 6, 16) for r in records)
        assert all(r.country == "SE" for r in records)
