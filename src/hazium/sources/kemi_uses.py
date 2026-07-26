"""Read crop uses out of KemI's free-text product `usage_areas`.

The Swedish product register states what a plant protection product is for as
a sentence, not as structured data: "Mot svampangrepp i odlingar av vete, rag,
ragvete, havre och korn." The crop is in there, but only as words.

This module turns those sentences into crop labels. Three decisions in it are
load-bearing, and each comes from a failure observed against the real register
rather than from anticipating one.

**Matching is exact against listed word forms, never a prefix test.** A prefix
test on ``bar`` (berries) also matches ``barn``, children, which appears in the
safety line "Ej for barn under tre ar". The same trap holds for ``lok`` (onion)
against ``lokal`` and ``kal`` (cabbage) against ``kalk``.

**Season prefixes are stripped before matching.** Swedish writes the sown
season into the crop word, so ``hostvete``, ``varvete`` and ``hostraps`` are the
ordinary spellings for winter wheat, spring wheat and winter rape. Missing them
undercounts precisely the crops Sweden grows most.

**Only cultivation contexts count as a crop.** The register uses the same
vocabulary for growing, for treating stored goods, and for post-harvest
handling of imports: "vid inlagring av spannmal, torkad frukt" is stored grain
and dried fruit, and "mognadsreglering av bananer och citrusfrukter" is
ripening imported bananas. Neither is a Swedish crop. The Swedish word for
cultivation, ``odling``, separates them, and it appears in 703 of the 870
usage-area strings on currently approved products.
"""

from __future__ import annotations

import re

#: Season prefixes stripped before a crop word is matched.
SEASON_PREFIXES: tuple[str, ...] = ("host", "var", "sommar", "vinter")

#: The Swedish stem for cultivation. Its presence is what distinguishes a crop
#: being grown from a commodity being stored or an import being ripened.
CULTIVATION_MARKER = "odling"

#: Readable crop label -> the diacritic-folded word forms that denote it.
#: Forms are matched whole; add inflections here rather than loosening the test.
CROP_FORMS: dict[str, tuple[str, ...]] = {
    "wheat": ("vete",),
    "triticale": ("ragvete",),
    "rye": ("rag",),
    "oats": ("havre",),
    "barley": ("korn",),
    "cereals (unspecified)": ("strasad", "strasaden", "spannmal"),
    "potato": ("potatis", "potatisen"),
    "sugar beet": ("sockerbeta", "sockerbetor", "sockerbetorna"),
    "oilseed rape": ("raps", "rapsen"),
    "turnip rape": ("rybs",),
    "maize": ("majs",),
    "fodder maize": ("fodermajs",),
    "apple": ("apple", "applen"),
    "pear": ("paron", "paronen"),
    "strawberry": ("jordgubbar", "jordgubbe", "jordgubbarna"),
    "raspberry": ("hallon", "hallonen"),
    "currant": ("vinbar", "vinbaren", "krusbar"),
    "peas": ("art", "arter", "arterna", "artor"),
    "beans": ("bona", "bonor", "bonorna"),
    "flax": ("lin", "linet"),
    "grass ley": ("vall", "vallar", "gravall", "gravallar", "betesvall", "slattervall"),
    "carrot": ("morot", "morotter"),
    "onion": ("lok", "loken", "kepalok"),
    "cabbage": ("kal", "kalen", "blomkal", "brysselkal", "broccoli"),
    "lettuce": ("sallat", "sallad"),
    "tomato": ("tomat", "tomater"),
    "cucumber": ("gurka", "gurkor"),
    "pepper": ("paprika",),
    "vegetables": ("gronsaker", "fruktgronsaker", "gronsakerna", "koksvaxter", "rotgronsaker"),
    "ornamentals": ("prydnadsvaxter", "prydnadsvaxt"),
    "nursery stock": ("plantskolevaxter", "plantskola"),
    "fruit (unspecified)": ("frukt", "frukter"),
    "berries (unspecified)": ("bar", "baren"),
}

#: Reverse index, built once. Word form -> crop label.
_FORM_TO_CROP: dict[str, str] = {form: crop for crop, forms in CROP_FORMS.items() for form in forms}

_FOLD = str.maketrans("åäöÅÄÖéÉüÜ", "aaoAAOeEuU")
_TOKEN_SPLIT = re.compile(r"[^a-z0-9]+")


def fold(text: str) -> str:
    """Lowercase and strip Swedish diacritics so word forms compare plainly."""
    return text.translate(_FOLD).lower()


def is_cultivation(text: str) -> bool:
    """Whether a usage-area sentence describes growing rather than storage.

    Args:
        text: One usage-area string as printed in the register.

    Returns:
        True when the sentence concerns a crop in the ground or under glass.
    """
    return CULTIVATION_MARKER in fold(text)


def extract_crops(text: str) -> frozenset[str]:
    """Crop labels named in one usage-area sentence, ignoring context.

    Matches whole words only, and retries each token with a season prefix
    removed, so ``hostvete`` resolves to wheat.

    Args:
        text: One usage-area string.

    Returns:
        Readable crop labels. Empty when the sentence names no known crop.
    """
    found: set[str] = set()
    for token in _TOKEN_SPLIT.split(fold(text)):
        if not token:
            continue
        crop = _FORM_TO_CROP.get(token)
        if crop is not None:
            found.add(crop)
            continue
        for prefix in SEASON_PREFIXES:
            if token.startswith(prefix):
                crop = _FORM_TO_CROP.get(token[len(prefix) :])
                if crop is not None:
                    found.add(crop)
                    break
    return frozenset(found)


def crops_grown(usage_areas: list[str]) -> frozenset[str]:
    """Crops a product is approved for, counting cultivation contexts only.

    Storage fumigation and post-harvest treatment of imports name crops too,
    but those are not crops grown here, so they are excluded. See the module
    docstring for why this distinction is not cosmetic.

    Args:
        usage_areas: Every usage-area string on one product registration.

    Returns:
        Readable crop labels the product is approved to be used on in the field
        or under glass.
    """
    found: set[str] = set()
    for area in usage_areas:
        text = str(area)
        if is_cultivation(text):
            found |= extract_crops(text)
    return frozenset(found)
