"""Adapter for KEMI's annual pesticide sales reports.

"Försålda kvantiteter av bekämpningsmedel" is the authoritative public
record of pesticide sales in Sweden; there is no open API (planned 2027 at
the earliest). Each annual report carries Tabell 3: tonnes of active
substance sold per year, covering roughly the preceding eight years.

Temporal semantics: every figure parsed from a report is stamped with
``known_at`` = the report's publication date (PDF creation date). The same
(substance, year) cell recurs across consecutive reports; parsing older
reports yields earlier ``known_at``, and revised figures surface as new
facts, never mutations.

Cell sentinels in Tabell 3:
    ``-``    explicit statement of zero sales -> a 0.0-tonne record
    ``*)``   quantity withheld as confidential -> no record
    (blank)  substance not on the market that year -> no record

Substance names are as printed (Swedish, occasionally with line-wrap
artifacts). Mapping names to CAS numbers is the resolve module's job, not
this adapter's; ids emitted here are provisional name-based identities.
"""

from __future__ import annotations

import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber

from hazium.models import SalesRecord
from hazium.resolve.ids import substance_node_id

COUNTRY = "SE"
REPORT_URL_TEMPLATE = (
    "https://www.kemi.se/webdav/files/Kemikaliestatistik/"
    "Bek%C3%A4mpningsmedel/forsalda_bkm_{year}.pdf"
)

# Words within this many points vertically belong to the same table row.
_ROW_TOLERANCE = 4.0
# Horizontal margin separating the name column from the year columns.
_COLUMN_MARGIN = 10.0

Word = dict[str, Any]  # pdfplumber word: {"text", "x0", "x1", "top", ...}


def report_url(year: int) -> str:
    """URL of the annual sales report covering ``year``."""
    return REPORT_URL_TEMPLATE.format(year=year)


def download_report(year: int, dest_dir: Path) -> Path:
    """Download the annual report for ``year`` into ``dest_dir``.

    Skips the download if the file already exists; reports are historical
    documents and do not change after publication.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"forsalda_bkm_{year}.pdf"
    if not dest.exists():
        urllib.request.urlretrieve(report_url(year), dest)
    return dest


def parse_sales_report(pdf_path: Path, known_at: date | None = None) -> list[SalesRecord]:
    """Extract all Tabell 3 sales figures from an annual report PDF.

    Args:
        pdf_path: A downloaded ``forsalda_bkm_{year}.pdf``.
        known_at: Publication date override. Defaults to the PDF's creation
            date, which is when the figures became publicly knowable.

    Returns:
        One record per (substance, year) cell that asserts a quantity,
        sorted by substance id and year.

    Raises:
        ValueError: If no publication date is available, or the PDF
            contains no recognizable Tabell 3.
    """
    rows: list[tuple[str, dict[int, str]]] = []
    with pdfplumber.open(pdf_path) as pdf:
        if known_at is None:
            known_at = _creation_date(pdf.metadata)
        in_table3 = False
        for page in pdf.pages:
            text = page.extract_text() or ""
            if "Tabell 3." in text:
                in_table3 = True
            if "Tabell 4." in text:
                in_table3 = False
            if in_table3:
                rows.extend(_parse_page_words(page.extract_words()))
    if not rows:
        raise ValueError(f"no Tabell 3 sales figures found in {pdf_path}")

    report_year = max(year for _, cells in rows for year in cells)
    source = f"kemi:forsalda:{report_year}"
    records = [
        SalesRecord(
            substance_id=substance_node_id(name=name),
            country=COUNTRY,
            year=year,
            tonnes_active_substance=tonnes,
            source=source,
            known_at=known_at,
        )
        for name, cells in rows
        for year, cell in sorted(cells.items())
        if (tonnes := _parse_quantity(cell)) is not None
    ]
    return sorted(records, key=lambda r: (r.substance_id, r.year))


def _parse_page_words(words: list[Word]) -> list[tuple[str, dict[int, str]]]:
    """Reconstruct table rows from positioned words on one page.

    Grid extraction is unreliable here (blank cells collapse, column lines
    vary between pages), so rows are rebuilt from word coordinates: header
    year positions anchor the columns, value words cluster into rows by
    vertical position, and name fragments attach to the nearest value row.
    Blank cells then simply produce no word, which is exactly their meaning.
    """
    header = [w for w in words if _is_year(w["text"])]
    if len(header) < 2:
        return []
    header_top = min(w["top"] for w in header)
    centers = {int(w["text"]): (w["x0"] + w["x1"]) / 2 for w in header}
    first_x = min(w["x0"] for w in header)
    last_x = max(w["x1"] for w in header)

    body = [w for w in words if w["top"] > header_top + _ROW_TOLERANCE * 2]
    values = [
        w
        for w in body
        if _is_cell(w["text"])
        and w["x1"] > first_x - _COLUMN_MARGIN
        and w["x0"] < last_x + _COLUMN_MARGIN
    ]
    names = [w for w in body if w["x1"] <= first_x - _COLUMN_MARGIN]

    rows: list[dict[str, Any]] = []
    for w in sorted(values, key=lambda w: w["top"]):
        if rows and abs(w["top"] - rows[-1]["top"]) < _ROW_TOLERANCE:
            rows[-1]["values"].append(w)
        else:
            rows.append({"top": w["top"], "values": [w], "name": []})
    if not rows:
        return []
    for w in sorted(names, key=lambda w: (w["top"], w["x0"])):
        nearest = min(rows, key=lambda r: abs(r["top"] - w["top"]))
        nearest["name"].append(w["text"])

    out: list[tuple[str, dict[int, str]]] = []
    for row in rows:
        name = " ".join(row["name"])
        if not name:
            continue
        cells: dict[int, str] = {}
        for w in row["values"]:
            center = (w["x0"] + w["x1"]) / 2
            year = min(centers, key=lambda y: abs(centers[y] - center))
            cells[year] = w["text"]
        out.append((name, cells))
    return out


def _parse_quantity(cell: str) -> float | None:
    """Tonnes asserted by a table cell, or None if nothing is asserted."""
    if cell == "-":
        return 0.0
    if cell == "*)":
        return None
    return float(cell.replace(",", "."))


def _is_year(text: str) -> bool:
    return text.isdigit() and len(text) == 4 and 1990 <= int(text) <= 2035


def _is_cell(text: str) -> bool:
    return text in ("-", "*)") or text.replace(",", "", 1).isdigit()


def _creation_date(metadata: dict[str, Any] | None) -> date:
    """Publication date from PDF metadata, e.g. ``D:20250616090351+02'00'``."""
    raw = (metadata or {}).get("CreationDate", "")
    digits = raw.removeprefix("D:")[:8]
    if len(digits) == 8 and digits.isdigit():
        return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
    raise ValueError("PDF has no parseable creation date; pass known_at explicitly")
