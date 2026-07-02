"""Register adapter: ingredient declaration parsing and product mapping.

Fixtures are verbatim API responses recorded 2026-07-03; no network calls.
"""

from datetime import date

from hazium.models import ProductIngredient
from hazium.sources.kemi_register import _parse_date, _parse_ingredient, _parse_product

SHIRLAN = {
    "godkännandeUpphörde": None,
    "produktnamnId": 3772,
    "godkänd": True,
    "utfasningFastslagen": False,
    "företag": [{"roll": "I", "företagsId": 530, "namn": "ISK Biosciences Europe N.V."}],
    "produktkod": "IKF-1216 500 SC",
    "tidigareGodkänd": False,
    "ärLågrisk": False,
    "verksammaÄmnen": ["Fluazinam (CAS-nr: 79622-59-6) 500 g/L"],
    "beslutId": 21139,
    "registreringsnummer": "3957",
    "användningsvillkor": [],
    "användningsförbud": False,
    "produktNamn": "Shirlan",
    "godkändTom": "2027-04-15T00:00:00.0000000",
    "produktId": 7757,
    "huvudgrupp": "Växtskyddsmedel",
    "objektTypId": 1,
    "underAnstånd": False,
    "användningsområde": ["Mot svampangrepp i odlingar av potatis och kepalök."],
}

SNAPSHOT = date(2026, 7, 3)


class TestIngredientParsing:
    def test_cas_and_concentration(self) -> None:
        assert _parse_ingredient("Fluazinam (CAS-nr: 79622-59-6) 500 g/L") == ProductIngredient(
            name="Fluazinam", cas_number="79622-59-6", concentration="500 g/L"
        )

    def test_no_cas_segment_yields_name_only(self) -> None:
        assert _parse_ingredient("Bacillus thuringiensis kurstaki ABTS-351") == (
            ProductIngredient(name="Bacillus thuringiensis kurstaki ABTS-351")
        )

    def test_invalid_cas_dropped_not_propagated(self) -> None:
        parsed = _parse_ingredient("Bogusamin (CAS-nr: 79622-59-7) 10 g/L")
        assert parsed.cas_number is None
        assert parsed.name == "Bogusamin"

    def test_missing_concentration(self) -> None:
        parsed = _parse_ingredient("Fluazinam (CAS-nr: 79622-59-6)")
        assert parsed.concentration is None


class TestProductParsing:
    def test_shirlan_maps_fully(self) -> None:
        product = _parse_product(SHIRLAN, SNAPSHOT)
        assert product.registration_number == "3957"
        assert product.name == "Shirlan"
        assert product.approved is True
        assert product.approval_expires == date(2027, 4, 15)
        assert product.ingredients[0].cas_number == "79622-59-6"
        assert product.usage_areas == ("Mot svampangrepp i odlingar av potatis och kepalök.",)
        assert product.source == "kemi:bkmreg"
        assert product.known_at == SNAPSHOT

    def test_facts_survive_missing_optionals(self) -> None:
        raw = dict(SHIRLAN, godkändTom=None, verksammaÄmnen=None, användningsområde=None)
        product = _parse_product(raw, SNAPSHOT)
        assert product.approval_expires is None
        assert product.ingredients == ()
        assert product.usage_areas == ()


def test_register_timestamp_to_date() -> None:
    assert _parse_date("2027-04-15T00:00:00.0000000") == date(2027, 4, 15)
    assert _parse_date(None) is None
