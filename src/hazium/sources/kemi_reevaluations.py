"""Hand-curated Swedish national regulatory review announcements.

Unlike KEMI's other sources (the register API, the annual sales PDFs), this
is not scraped or programmatically fetched: KEMI publishes reevaluation
("omprövning") announcements as periodic news articles on kemi.se, with no
structured export or API. Each entry below is individually verified against its cited source URL,
dated to the announcement date, with substance identity (CAS numbers)
cross-checked against KEMI's own register data, never taken from the
announcement text or memory.

This is a real, dated *Swedish national* regulatory signal that EU PPDB
cannot see (it operates at EU level only). It is what actually connects the
graph to fluazinam's real 2026 controversy: a formal review is a real event,
distinct from and earlier than an actual withdrawal, and should not be
conflated with one -- see ``models.RegulatoryEventKind.REEVALUATION_STARTED``
vs. ``NON_RENEWAL``/``WITHDRAWAL``. Whether and how to include this weaker,
earlier signal in a supervised label is a framing decision made where the
label is defined (``ml/dataset.py``), not here: this module only asserts
that the review started, on the date it started.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from hazium.models import RegulatoryEvent, RegulatoryEventKind
from hazium.resolve.ids import safe_substance_node_id

SOURCE = "kemi:reevaluation-announcements"
JURISDICTION = "SE"


@dataclass(frozen=True)
class _Announcement:
    """One KEMI news announcement of a product-approval review."""

    event_date: date
    url: str
    substances: tuple[tuple[str, str], ...]  # (name, CAS) -- CAS verified against the register
    product_count: int
    decision_deadline: date | None


# CAS numbers cross-checked against data/processed/kemi_register_substances.jsonl
# (KEMI's own register data), not taken from the announcement or memory.
_ANNOUNCEMENTS: tuple[_Announcement, ...] = (
    _Announcement(
        event_date=date(2025, 11, 20),
        url=(
            "https://www.kemi.se/arkiv/nyhetsarkiv/nyheter/"
            "2025-11-20-vaxtskyddsmedel-som-kan-bilda-tfa-omprovas-for-att-skydda-grundvattnet"
        ),
        substances=(
            ("Fluazinam", "79622-59-6"),
            ("Fluopyram", "658066-35-4"),
            ("Diflufenikan", "83164-33-4"),
            ("Mefentriflukonazol", "1417782-03-6"),
            ("Tau-fluvalinat", "102851-06-9"),
            ("Flonikamid", "158062-67-0"),
        ),
        product_count=38,
        decision_deadline=date(2028, 4, 30),
    ),
)


def regulatory_events() -> list[RegulatoryEvent]:
    """One ``REEVALUATION_STARTED`` fact per substance per announcement.

    The decision deadline is not encoded as an event: it is a *target* date
    for a future decision that has not happened, not a realized fact, and
    asserting it as one would invent an event that hasn't occurred.
    """
    events = []
    for announcement in _ANNOUNCEMENTS:
        for name, cas in announcement.substances:
            substance_id = safe_substance_node_id(cas_number=cas, name=name)
            events.append(
                RegulatoryEvent(
                    substance_id=substance_id,
                    kind=RegulatoryEventKind.REEVALUATION_STARTED,
                    jurisdiction=JURISDICTION,
                    event_date=announcement.event_date,
                    source=SOURCE,
                    known_at=announcement.event_date,
                )
            )
    return events
