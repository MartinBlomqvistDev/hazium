"""Adapter for ECHA's Annex VI to CLP harmonised classification list.

ECHA CHEM (the 2025 successor to the standalone C&L Inventory) exposes two
very different things. The self-classified inventory holds ~7M
company-notified classifications across ~350k substances: self-reported,
noisy, no clean per-entry provenance, and reachable only through an Angular
module-federation SPA whose data call sits behind a terms-of-use gate, with
no documented public API. Annex VI holds the ~4,400 *harmonised*
classifications: legally-binding decisions adopted through CLP Adaptations to
Technical Progress (ATPs), published by ECHA as a single small Excel file.
This adapter uses the latter: it is the regulatory-decision layer the
manifesto wants fused with sales/register/toxicological evidence, curated
rather than crowd-sourced, and small enough to reason about directly.

The workbook has two sheets with identical columns: ``ATP23`` (the current
consolidated Table 3 snapshot) and ``History`` (one row per Index No x ATP
revision since CLP Regulation 1272/2008 itself). Only ``History`` is parsed
here: it is the temporal source of truth, dating each classification
*version* to the ATP that set it (via the ``In application`` column), rather
than collapsing everything to one snapshot date the way a live register
would. This is what lets fluazinam's 2014/2015 classification survive a
pre-2023 ``as_of`` view as a real dated fact, not a frozen snapshot.

Access constraint: echa.europa.eu sits behind an Azure WAF JS challenge, so
an automated ``httpx``/``requests`` GET receives the challenge page, not the
file. This adapter therefore reads a pinned local snapshot rather than
fetching live -- the standard pattern for WAF-protected government sources,
and arguably better for reproducibility regardless. Fetch it once manually
from ``SOURCE_URL`` into ``DEFAULT_SNAPSHOT``.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import openpyxl

from hazium.models import HazardClassification
from hazium.resolve.ids import safe_substance_node_id

SOURCE = "echa:clp-annex-vi"
SOURCE_URL = "https://echa.europa.eu/documents/10162/17218/annex_vi_clp_table_atp23_en.xlsx"
DEFAULT_SNAPSHOT = Path("data/raw/annex_vi_clp_table_atp23_en.xlsx")

_HISTORY_SHEET = "History"


@dataclass(frozen=True)
class _HistoryRow:
    """One (Index No, ATP) revision from the ``History`` sheet."""

    index_no: str
    atp: str
    celex: str
    name: str
    cas_number: str | None
    hazard_classes: tuple[str, ...]
    hazard_codes: tuple[str, ...]
    known_at: date


def load(xlsx_path: Path) -> list[_HistoryRow]:
    """Parse every row of the ``History`` sheet.

    Rows with no name, no ``In application`` date, or no hazard statement
    code are dropped: without all three there is nothing dateable and
    identifiable to assert. A handful of rows are notes-only or
    labelling-only revisions with no classification change.
    """
    workbook = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    try:
        sheet = workbook[_HISTORY_SHEET]
        rows_iter = sheet.iter_rows(values_only=True)
        header = next(rows_iter)
        idx = {name: i for i, name in enumerate(header) if name}
        rows = []
        for row in rows_iter:
            name = row[idx["Chemical Name"]]
            known_at = _parse_date(row[idx["In application"]])
            hazard_codes = _split(row[idx["Classification Hazard Statement Code(s)"]])
            if not name or not known_at or not hazard_codes:
                continue
            rows.append(
                _HistoryRow(
                    index_no=row[idx["Index No"]],
                    atp=row[idx["ATP"]],
                    celex=row[idx["CELEX"]],
                    name=name,
                    cas_number=_clean_cas(row[idx["CAS No"]]),
                    hazard_classes=_split(row[idx["Hazard Class and Category Code(s)"]]),
                    hazard_codes=hazard_codes,
                    known_at=known_at,
                )
            )
        return rows
    finally:
        workbook.close()


def _split(value: Any) -> tuple[str, ...]:
    """Multi-value cells are newline-separated (one substance, several codes)."""
    if not value:
        return ()
    return tuple(part.strip() for part in str(value).splitlines() if part.strip())


def _clean_cas(value: Any) -> str | None:
    """Group/UVCB entries use '-' for CAS No; treat that as absent, not a value."""
    text = str(value).strip() if value else None
    if not text or text == "-":
        return None
    return text


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def classifications_from(rows: list[_HistoryRow]) -> list[HazardClassification]:
    """One ``HazardClassification`` fact per (row, H-statement code).

    ``substance_id`` is resolved at ingestion via CAS-priority id (falling
    back to a name-based id for the group entries that carry none), matching
    the precedent set by ``SalesRecord``/``DegradationLink``: a real CAS
    number here lands on exactly the same node id KEMI/OpenFoodTox already
    produced for that substance, without any graph-side resolution step.

    Hazard class and H-code lists are positionally paired when their lengths
    match, which is the common case (one class per H-statement). When they
    don't -- CLP notes and supplementary hazard statements can desync the two
    lists -- codes are emitted without a paired ``hazard_class`` rather than
    guessing a wrong pairing.
    """
    classifications = []
    for row in rows:
        substance_id = safe_substance_node_id(cas_number=row.cas_number, name=row.name)
        paired: tuple[str | None, ...] = (
            row.hazard_classes
            if len(row.hazard_classes) == len(row.hazard_codes)
            else tuple(None for _ in row.hazard_codes)
        )
        for hazard_code, hazard_class in zip(row.hazard_codes, paired, strict=True):
            classifications.append(
                HazardClassification(
                    substance_id=substance_id,
                    hazard_code=hazard_code,
                    hazard_class=hazard_class,
                    system="CLP",
                    atp=row.atp,
                    celex=row.celex,
                    source=SOURCE,
                    known_at=row.known_at,
                )
            )
    return classifications


#: The CLP Regulation itself, which defines the H-statement codes. Taken from
#: the Annex VI export's own EUR-Lex Link column rather than composed by hand.
CLP_REGULATION_URL = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32008R1272"


def hazard_class_by_code(rows: list[_HistoryRow]) -> dict[str, str]:
    """Map each H-statement code to the CLP hazard class it denotes.

    An H-code on its own ("H400") says nothing to a reader; the class it stands
    for ("Aquatic Acute 1") does. Annex VI carries both, positionally paired,
    so the mapping is derived from the data rather than transcribed from
    knowledge of CLP.

    Rows whose two lists differ in length are skipped, exactly as
    ``classifications_from`` skips them: CLP notes and supplementary statements
    desync the lists, and a wrong pairing is worse than no pairing. Where a code
    appears against more than one class across the table, the most frequent
    pairing wins, and codes are compared on their base form so that qualified
    variants ("H361d ***") resolve with their parent.

    Args:
        rows: Parsed Annex VI history rows.

    Returns:
        Base H-code to hazard class, e.g. ``{"H400": "Aquatic Acute 1"}``.
    """
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        if len(row.hazard_classes) != len(row.hazard_codes):
            continue
        for code, hazard_class in zip(row.hazard_codes, row.hazard_classes, strict=True):
            base = code.split()[0] if code.split() else code
            if base and hazard_class:
                counts[base][hazard_class] += 1
    return {code: tally.most_common(1)[0][0] for code, tally in counts.items() if tally}
