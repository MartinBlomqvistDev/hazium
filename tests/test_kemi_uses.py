"""Tests for crop extraction from KemI's free-text usage areas.

Every case here is a real string from the register, or a minimal reduction of
one. The three interesting tests are the regressions: season prefixes, the
``barn``/``bar`` collision, and the storage-versus-cultivation split.
"""

from hazium.sources.kemi_uses import crops_grown, extract_crops, is_cultivation


def test_extracts_the_cereal_list_the_register_actually_prints() -> None:
    text = "Mot svampangrepp i odlingar av vete, råg, rågvete, havre och korn."
    assert extract_crops(text) == frozenset({"wheat", "rye", "triticale", "oats", "barley"})


def test_season_prefixed_crops_resolve_to_the_crop() -> None:
    """Swedish writes the sown season into the word: hostvete is winter wheat.

    A prefix-based matcher misses every one of these, which silently
    undercounts the crops Sweden grows most.
    """
    text = "Mot ogräs i odlingar av höstvete, höstråg, höstrågvete och vårvete."
    assert extract_crops(text) == frozenset({"wheat", "rye", "triticale"})


def test_hostraps_resolves_to_oilseed_rape() -> None:
    assert extract_crops("Mot örtogräs i odlingar av höstraps.") == frozenset({"oilseed rape"})


def test_barn_is_not_berries() -> None:
    """The safety line 'Ej for barn under tre ar' must not read as a crop.

    ``bar`` (berries) is a prefix of ``barn`` (children). This is why matching
    is exact against listed forms rather than by prefix.
    """
    assert extract_crops("Ej för barn under tre år.") == frozenset()


def test_lokal_is_not_onion_and_kalk_is_not_cabbage() -> None:
    assert extract_crops("Endast för lokal behandling med kalk.") == frozenset()


def test_cultivation_is_detected_by_the_odling_stem() -> None:
    assert is_cultivation("Mot svampangrepp i odlingar av potatis.")
    assert is_cultivation("Mot gråmögel i växthusodling av tomat.")
    assert not is_cultivation("Mot insektsangrepp vid inlagring av spannmål.")
    assert not is_cultivation("För mognadsreglering av bananer och citrusfrukter.")


def test_stored_goods_are_not_counted_as_grown_crops() -> None:
    """Stored grain and dried fruit name crops, but are not crops grown here."""
    areas = ["Mot insektsangrepp vid inlagring av spannmål, torkad frukt, torkade bär."]
    assert crops_grown(areas) == frozenset()


def test_stored_potato_is_not_a_potato_crop() -> None:
    assert crops_grown(["För groningshämmande behandling av lagrad potatis."]) == frozenset()


def test_grown_potato_is_counted() -> None:
    assert crops_grown(["Mot svampangrepp i odlingar av potatis."]) == frozenset({"potato"})


def test_a_product_with_mixed_contexts_keeps_only_the_grown_crop() -> None:
    areas = [
        "Mot svampangrepp i odlingar av potatis.",
        "Mot insektsangrepp vid inlagring av spannmål.",
    ]
    assert crops_grown(areas) == frozenset({"potato"})


def test_unknown_text_yields_nothing_rather_than_guessing() -> None:
    assert extract_crops("Mot slembildande mikroorganismer i maskinsystem.") == frozenset()
