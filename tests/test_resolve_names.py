"""Substance name resolution: the three matching tiers and honest refusal."""

from datetime import date

import pytest

from hazium.models import Substance
from hazium.resolve.names import SubstanceResolver, normalize_name

KNOWN = date(2026, 7, 3)


def _substance(name: str, cas: str | None) -> Substance:
    return Substance(name=name, cas_number=cas, source="test", known_at=KNOWN)


@pytest.fixture
def resolver() -> SubstanceResolver:
    return SubstanceResolver(
        [
            _substance("Fluazinam", "79622-59-6"),
            _substance("3-Jod-2-propynylbutylkarbamat (IPBC)", "55406-53-6"),
            _substance("Azoxistrobin", "131860-33-8"),
            _substance("Fettsyror (C8-C18), kaliumsalter", None),
        ]
    )


class TestNormalize:
    def test_strips_hyphens_spaces_case(self) -> None:
        assert normalize_name("3-Jod-2-propynyl butylkarbamat") == "3jod2propynylbutylkarbamat"

    def test_line_wrap_double_hyphen_collapses(self) -> None:
        assert normalize_name("Fluaz--inam") == normalize_name("Fluazinam")


class TestResolve:
    def test_exact_match_yields_cas_id(self, resolver: SubstanceResolver) -> None:
        r = resolver.resolve("fluazinam")
        assert r.substance_id == "substance:cas:79622-59-6"
        assert r.method == "exact"
        assert r.matched

    def test_qualifier_stripped_match(self, resolver: SubstanceResolver) -> None:
        # sales prose omits the register's trailing "(IPBC)"
        r = resolver.resolve("3-jod-2-propynylbutylkarbamat")
        assert r.cas_number == "55406-53-6"
        assert r.method == "qualifier"

    def test_verified_alias(self, resolver: SubstanceResolver) -> None:
        r = resolver.resolve("Azoxystrobin")  # English spelling
        assert r.substance_id == "substance:cas:131860-33-8"
        assert r.method == "alias"

    def test_matched_but_cas_less_substance(self, resolver: SubstanceResolver) -> None:
        r = resolver.resolve("Fettsyror (C8-C18), kaliumsalter")
        assert r.matched
        assert r.cas_number is None
        assert r.substance_id.startswith("substance:name:")

    def test_unknown_stays_provisional(self, resolver: SubstanceResolver) -> None:
        r = resolver.resolve("Glyfosat")  # parent acid, only salts in register
        assert not r.matched
        assert r.method == "provisional"
        assert r.substance_id == "substance:name:glyfosat"


def test_cas_bearing_entry_wins_over_cas_less_on_key_collision() -> None:
    resolver = SubstanceResolver(
        [
            _substance("Koppar", None),
            _substance("Koppar", "7440-50-8"),
        ]
    )
    assert resolver.resolve("koppar").cas_number == "7440-50-8"


def test_unverified_alias_is_not_invented() -> None:
    # trifloxystrobin has no register candidate here; must not be forced
    resolver = SubstanceResolver([_substance("Fluazinam", "79622-59-6")])
    assert not resolver.resolve("Trifloxystrobin").matched
