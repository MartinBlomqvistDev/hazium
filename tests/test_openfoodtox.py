"""OpenFoodTox adapter: pure transforms over a hand-built index.

No real spreadsheet is needed for these: substances_from/degradation_links_from/
assessments_from are pure transforms over ``OpenFoodToxIndex``, by design (see
module docstring in sources/openfoodtox.py). The identity values used here
(fluazinam, TFA, flufenacet) are the real CAS/EC numbers verified against the
actual OpenFoodTox 3.0 export during development.
"""

from datetime import date

from hazium.sources.openfoodtox import (
    OpenFoodToxIndex,
    _SubstanceIdentity,
    _parse_date,
    assessments_from,
    degradation_links_from,
    substances_from,
)

PUBLISHED = date(2026, 4, 30)

FLUAZINAM_UUID = "sub-fluazinam"
TFA_UUID = "sub-tfa"
FLUFENACET_UUID = "sub-flufenacet"
GHOST_UUID = "sub-not-in-index"


def _index(**overrides) -> OpenFoodToxIndex:
    base = dict(
        substances={
            FLUAZINAM_UUID: _SubstanceIdentity("Fluazinam", "79622-59-6", "616-712-5", None),
            TFA_UUID: _SubstanceIdentity("Trifluoroacetic acid", "76-05-1", "200-929-3", None),
            FLUFENACET_UUID: _SubstanceIdentity("Flufenacet", "142459-58-3", None, None),
        },
        degradation_pairs=[(FLUFENACET_UUID, TFA_UUID)],
        assessments=[
            {
                "dossier_uuid": "dossier-1",
                "subject_uuid": FLUAZINAM_UUID,
                "published_at": date(2008, 3, 26),
                "title": "Conclusion regarding fluazinam",
                "doi": "doi:10.2903/j.efsa.2008.137r",
            }
        ],
    )
    base.update(overrides)
    return OpenFoodToxIndex(**base)


class TestSubstancesFrom:
    def test_yields_one_substance_per_identity(self) -> None:
        substances = substances_from(_index(), known_at=PUBLISHED)
        assert len(substances) == 3

    def test_cas_priority_id_and_fields(self) -> None:
        substances = {s.name: s for s in substances_from(_index(), known_at=PUBLISHED)}
        fluazinam = substances["Fluazinam"]
        assert fluazinam.cas_number == "79622-59-6"
        assert fluazinam.ec_number == "616-712-5"
        assert fluazinam.source == "efsa:openfoodtox"
        assert fluazinam.known_at == PUBLISHED

    def test_duplicate_node_ids_deduplicated(self) -> None:
        index = _index(
            substances={
                FLUAZINAM_UUID: _SubstanceIdentity("Fluazinam", "79622-59-6", None, None),
                "sub-fluazinam-dup": _SubstanceIdentity("Fluazinam", "79622-59-6", None, None),
            },
            degradation_pairs=[],
            assessments=[],
        )
        assert len(substances_from(index, known_at=PUBLISHED)) == 1

    def test_malformed_cas_preserved_on_record_but_not_node_id(self) -> None:
        index = _index(
            substances={
                "sub-bad": _SubstanceIdentity("Mystery substance", "999999-91-4", None, None)
            },
            degradation_pairs=[],
            assessments=[],
        )
        substances = substances_from(index, known_at=PUBLISHED)
        assert substances[0].cas_number == "999999-91-4"  # raw source claim kept


class TestDegradationLinksFrom:
    def test_resolves_both_endpoints_to_cas_ids(self) -> None:
        links = degradation_links_from(_index(), fallback_known_at=PUBLISHED)
        assert len(links) == 1
        assert links[0].parent_substance_id == "substance:cas:142459-58-3"
        assert links[0].metabolite_substance_id == "substance:cas:76-05-1"

    def test_falls_back_to_export_date_when_parent_has_no_dated_assessment(self) -> None:
        # The fixture's one assessment is for fluazinam, not flufenacet (the
        # parent in the only degradation pair), so no earlier date exists.
        links = degradation_links_from(_index(), fallback_known_at=PUBLISHED)
        assert links[0].known_at == PUBLISHED

    def test_back_dated_to_parents_earliest_assessment_when_one_exists(self) -> None:
        earlier = date(2008, 3, 26)
        index = _index(
            degradation_pairs=[(FLUAZINAM_UUID, TFA_UUID)],
            assessments=[
                {
                    "dossier_uuid": "dossier-1",
                    "subject_uuid": FLUAZINAM_UUID,
                    "published_at": earlier,
                    "title": "Conclusion regarding fluazinam",
                    "doi": "doi:10.2903/j.efsa.2008.137r",
                },
                {
                    "dossier_uuid": "dossier-2",
                    "subject_uuid": FLUAZINAM_UUID,
                    "published_at": date(2015, 1, 1),
                    "title": "Later conclusion regarding fluazinam",
                    "doi": "doi:10.2903/j.efsa.2015.001",
                },
            ],
        )
        links = degradation_links_from(index, fallback_known_at=PUBLISHED)
        assert links[0].known_at == earlier  # earliest of the parent's assessments, not export date

    def test_pair_referencing_unindexed_substance_is_dropped(self) -> None:
        index = _index(degradation_pairs=[(FLUFENACET_UUID, GHOST_UUID)])
        assert degradation_links_from(index, fallback_known_at=PUBLISHED) == []


class TestAssessmentsFrom:
    def test_dated_document_linked_to_subject(self) -> None:
        documents = assessments_from(_index())
        assert len(documents) == 1
        doc = documents[0]
        assert doc.subject_substance_id == "substance:cas:79622-59-6"
        assert doc.known_at == date(2008, 3, 26)
        assert doc.published_at == date(2008, 3, 26)

    def test_doi_becomes_id_and_url(self) -> None:
        doc = assessments_from(_index())[0]
        assert doc.id == "10.2903/j.efsa.2008.137r"
        assert doc.url == "https://doi.org/10.2903/j.efsa.2008.137r"

    def test_missing_doi_falls_back_to_dossier_uuid(self) -> None:
        index = _index(
            assessments=[
                {
                    "dossier_uuid": "12345678-abcd",
                    "subject_uuid": FLUAZINAM_UUID,
                    "published_at": date(2020, 1, 1),
                    "title": "Undated-DOI opinion",
                    "doi": None,
                }
            ]
        )
        doc = assessments_from(index)[0]
        assert doc.id == "efsa-dossier-12345678"
        assert doc.url is None

    def test_assessment_referencing_unindexed_subject_is_dropped(self) -> None:
        index = _index(
            assessments=[
                {
                    "dossier_uuid": "x",
                    "subject_uuid": GHOST_UUID,
                    "published_at": date(2020, 1, 1),
                    "title": "Orphan opinion",
                    "doi": None,
                }
            ]
        )
        assert assessments_from(index) == []


class TestParseDate:
    def test_iso_string(self) -> None:
        assert _parse_date("2008-03-26") == date(2008, 3, 26)

    def test_date_object_passthrough(self) -> None:
        assert _parse_date(date(2008, 3, 26)) == date(2008, 3, 26)

    def test_none_and_garbage_yield_none(self) -> None:
        assert _parse_date(None) is None
        assert _parse_date("not-a-date") is None
