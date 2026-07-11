"""Contract tests: facts are immutable, strict, and identity is validated."""

from datetime import date

import pytest
from pydantic import ValidationError

from hazium.models import NodeType, Node
from hazium.resolve.ids import is_valid_cas, safe_substance_node_id, substance_node_id


def _node() -> Node:
    return Node(
        id="substance:cas:79622-59-6",
        type=NodeType.SUBSTANCE,
        label="fluazinam",
        source="test",
        known_at=date(2008, 1, 1),
    )


def test_facts_are_frozen() -> None:
    node = _node()
    with pytest.raises(ValidationError):
        node.label = "renamed"  # type: ignore[misc]


def test_facts_forbid_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Node(
            id="x",
            type=NodeType.SUBSTANCE,
            label="x",
            source="test",
            known_at=date(2020, 1, 1),
            surprise="field",  # type: ignore[call-arg]
        )


class TestCasValidation:
    def test_real_cas_numbers_validate(self) -> None:
        assert is_valid_cas("79622-59-6")  # fluazinam
        assert is_valid_cas("76-05-1")  # trifluoroacetic acid (TFA)

    def test_wrong_check_digit_rejected(self) -> None:
        assert not is_valid_cas("79622-59-7")

    def test_malformed_strings_rejected(self) -> None:
        assert not is_valid_cas("fluazinam")
        assert not is_valid_cas("79622596")
        assert not is_valid_cas("79622-596-")


class TestSubstanceNodeId:
    def test_cas_takes_priority(self) -> None:
        assert (
            substance_node_id(cas_number="79622-59-6", name="Fluazinam")
            == "substance:cas:79622-59-6"
        )

    def test_name_fallback_is_slugged(self) -> None:
        assert substance_node_id(name="Trifluoroacetic Acid") == (
            "substance:name:trifluoroacetic-acid"
        )

    def test_invalid_cas_raises(self) -> None:
        with pytest.raises(ValueError):
            substance_node_id(cas_number="79622-59-7")

    def test_no_identifier_raises(self) -> None:
        with pytest.raises(ValueError):
            substance_node_id()


class TestSafeSubstanceNodeId:
    def test_valid_cas_behaves_like_strict_version(self) -> None:
        assert safe_substance_node_id("79622-59-6", "Fluazinam") == "substance:cas:79622-59-6"

    def test_malformed_cas_falls_back_to_name(self) -> None:
        # real-world register/export noise: encoding artifacts, typos
        assert safe_substance_node_id("58-89-2", "Lindane") == "substance:name:lindane"

    def test_no_cas_falls_back_to_name(self) -> None:
        assert safe_substance_node_id(None, "Fluazinam") == "substance:name:fluazinam"

    def test_no_identifier_at_all_still_raises(self) -> None:
        with pytest.raises(ValueError):
            safe_substance_node_id(None, None)
