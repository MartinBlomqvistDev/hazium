"""Canonical identifiers and identifier validation.

Entity resolution is a first-class module: knowledge graphs fail at their
joins, not at their models. Canonical node ids are derived from existing
vocabularies in fixed priority order, never invented.
"""

from __future__ import annotations


def is_valid_cas(cas_number: str) -> bool:
    """Validate a CAS Registry Number, including its check digit.

    The check digit is the weighted sum of the preceding digits (rightmost
    digit weight 1, increasing leftwards) modulo 10.

    Args:
        cas_number: Candidate string, e.g. ``"79622-59-6"``.

    Returns:
        True if the string is a structurally valid CAS number.
    """
    parts = cas_number.split("-")
    if len(parts) != 3:
        return False
    head, mid, check = parts
    if not (head.isdigit() and mid.isdigit() and check.isdigit()):
        return False
    if not (2 <= len(head) <= 7 and len(mid) == 2 and len(check) == 1):
        return False
    digits = head + mid
    weighted = sum(int(d) * w for w, d in enumerate(reversed(digits), start=1))
    return weighted % 10 == int(check)


def substance_node_id(cas_number: str | None = None, name: str | None = None) -> str:
    """Derive the canonical node id for a substance.

    Priority: CAS number, then name slug. A name-based id is a provisional
    identity awaiting resolution against a registry.

    Raises:
        ValueError: If no identifier is provided, or the CAS number is invalid.
    """
    if cas_number is not None:
        if not is_valid_cas(cas_number):
            raise ValueError(f"invalid CAS number: {cas_number!r}")
        return f"substance:cas:{cas_number}"
    if name:
        slug = "-".join(name.lower().split())
        return f"substance:name:{slug}"
    raise ValueError("substance requires a CAS number or a name")


def product_node_id(country: str, product_name_id: int) -> str:
    """Canonical node id for a registered product, e.g. 'product:se:3772'.

    Keyed on the register's ``product_name_id``, not the registration number,
    which is shared across biocide product families.
    """
    return f"product:{country.lower()}:{product_name_id}"


def country_node_id(country: str) -> str:
    """Canonical node id for a country, e.g. 'country:SE'."""
    return f"country:{country.upper()}"


def document_node_id(document_id: str) -> str:
    """Canonical node id for a source document, e.g. 'document:10.2903/j.efsa.2008.137r'."""
    return f"document:{document_id}"


def safe_substance_node_id(cas_number: str | None, name: str | None) -> str:
    """Like ``substance_node_id``, but never raises on a malformed CAS.

    Real-world registries occasionally contain CAS values that fail
    check-digit validation (encoding artifacts, placeholders, typos): a
    fraction of a percent, but enough that treating it as fatal would abort
    ingestion of an otherwise-good source. The record's ``cas_number`` field
    still preserves the source's raw claim; only graph identity falls back
    to the name here. Any caller deriving a substance's node id from an
    already-stored ``Substance`` record should use this, not the strict
    version, since a record accepted at ingestion time must remain buildable.
    """
    try:
        return substance_node_id(cas_number=cas_number, name=name)
    except ValueError:
        return substance_node_id(name=name)
