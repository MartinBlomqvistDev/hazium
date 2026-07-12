"""KEMI reevaluation announcements: hand-curated facts, not a parser -- tests
check the emitted RegulatoryEvent shape, not any parsing logic.
"""

from datetime import date

from hazium.models import RegulatoryEventKind
from hazium.sources.kemi_reevaluations import regulatory_events


class TestRegulatoryEvents:
    def test_yields_one_event_per_substance_in_the_announcement(self) -> None:
        events = regulatory_events()
        assert len(events) == 6

    def test_all_events_are_reevaluation_started_in_sweden(self) -> None:
        events = regulatory_events()
        assert all(e.kind == RegulatoryEventKind.REEVALUATION_STARTED for e in events)
        assert all(e.jurisdiction == "SE" for e in events)

    def test_fluazinam_is_included_with_correct_cas(self) -> None:
        events = {e.substance_id: e for e in regulatory_events()}
        assert "substance:cas:79622-59-6" in events
        fluazinam = events["substance:cas:79622-59-6"]
        assert fluazinam.event_date == date(2025, 11, 20)
        assert fluazinam.known_at == date(2025, 11, 20)

    def test_all_six_named_substances_present(self) -> None:
        events = regulatory_events()
        substance_ids = {e.substance_id for e in events}
        assert substance_ids == {
            "substance:cas:79622-59-6",  # fluazinam
            "substance:cas:658066-35-4",  # fluopyram
            "substance:cas:83164-33-4",  # diflufenikan
            "substance:cas:1417782-03-6",  # mefentriflukonazol
            "substance:cas:102851-06-9",  # tau-fluvalinat
            "substance:cas:158062-67-0",  # flonikamid
        }

    def test_source_is_kemi_reevaluation_announcements(self) -> None:
        assert all(e.source == "kemi:reevaluation-announcements" for e in regulatory_events())
