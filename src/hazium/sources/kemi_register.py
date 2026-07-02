"""Adapter for KEMI's pesticide register (bekämpningsmedelsregistret).

The public register UI at kemi.se/bkmreg is a Sitevision webapp backed by an
undocumented JSON API under ``/appresource/{page}/{portlet}/``. The routes
were recovered from the webapp bundle; they are the same calls the official
UI makes, but they are not a contract, so this adapter validates responses
and fails loudly on shape changes.

Two surfaces are used:

* ``/metadata/verksammaaemnen`` and ``/metadata/verksammaaemnencas`` share
  one id space, so joining them yields the register's complete substance
  name-to-CAS mapping. The CAS list is fetched with ``query=-`` because
  every CAS number contains a hyphen.
* ``/search/basic`` with an empty query enumerates every registered product,
  paginated, including approval state and declared active substances.

The register is a live database without publication history, so every fact
gets ``known_at`` = the snapshot date.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import date
from typing import Any

from hazium.models import ProductIngredient, ProductRegistration, Substance
from hazium.resolve.ids import is_valid_cas

SOURCE = "kemi:bkmreg"
COUNTRY = "SE"
BASE_URL = "https://www.kemi.se/appresource/4.f2282a218fe7e43b374b6b/12.6d6369f7195b2763b9e3905b"
_USER_AGENT = "hazium/0.0.1 (research; github.com/MartinBlomqvistDev/hazium)"
_PAGE_SIZE = 100


def fetch_substances(known_at: date | None = None) -> list[Substance]:
    """The register's complete substance list with CAS numbers where declared.

    Substances without a CAS number (chiefly microorganisms) are returned
    with ``cas_number=None``. CAS numbers that fail check-digit validation
    are rejected loudly rather than silently kept.
    """
    known_at = known_at or date.today()
    names = {row["id"]: row["text"] for row in _get("/metadata/verksammaaemnen")}
    cas = {row["id"]: row["text"] for row in _get("/metadata/verksammaaemnencas", query="-")}
    for substance_id, cas_number in cas.items():
        if not is_valid_cas(cas_number):
            raise ValueError(f"register returned invalid CAS {cas_number!r} (id {substance_id})")
    return [
        Substance(name=name, cas_number=cas.get(sid), source=SOURCE, known_at=known_at)
        for sid, name in sorted(names.items())
    ]


def fetch_products(known_at: date | None = None) -> list[ProductRegistration]:
    """Every product registration in the register, via paginated basic search."""
    known_at = known_at or date.today()
    products: list[ProductRegistration] = []
    page = 1
    while True:
        payload = _get("/search/basic", query="", page=str(page), pageSize=str(_PAGE_SIZE))
        for raw in payload["resultat"]:
            products.append(_parse_product(raw, known_at))
        total = payload["pagingResponse"]["total"]
        if page * _PAGE_SIZE >= total:
            return products
        page += 1


def _parse_product(raw: dict[str, Any], known_at: date) -> ProductRegistration:
    return ProductRegistration(
        registration_number=str(raw["registreringsnummer"]),
        name=raw["produktNamn"],
        country=COUNTRY,
        main_group=raw["huvudgrupp"] or "",
        approved=raw["godkänd"],
        previously_approved=raw["tidigareGodkänd"],
        usage_ban=raw["användningsförbud"],
        approval_expires=_parse_date(raw.get("godkändTom")),
        ingredients=tuple(_parse_ingredient(s) for s in raw.get("verksammaÄmnen") or []),
        usage_areas=tuple(raw.get("användningsområde") or []),
        source=SOURCE,
        known_at=known_at,
    )


def _parse_ingredient(declaration: str) -> ProductIngredient:
    """Split a declared ingredient like ``'Fluazinam (CAS-nr: 79622-59-6) 500 g/L'``.

    Declarations without a CAS segment (microorganisms, some mixtures) yield
    a name-only ingredient. A malformed CAS is kept as None rather than
    propagated; identity repair is the resolve module's job.
    """
    name, sep, rest = declaration.partition(" (CAS-nr: ")
    if not sep:
        return ProductIngredient(name=declaration.strip())
    cas_number, _, concentration = rest.partition(")")
    cas_number = cas_number.strip()
    return ProductIngredient(
        name=name.strip(),
        cas_number=cas_number if is_valid_cas(cas_number) else None,
        concentration=concentration.strip() or None,
    )


def _parse_date(value: str | None) -> date | None:
    """``'2027-04-15T00:00:00.0000000'`` -> date(2027, 4, 15)."""
    if not value:
        return None
    return date.fromisoformat(value[:10])


def _get(route: str, **params: str) -> Any:
    url = BASE_URL + route
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request) as response:
        return json.load(response)
