"""Resolve substance names to canonical identifiers against the register.

Knowledge graphs fail at their joins. The sales reports name substances in
running Swedish prose ("Fluazinam", "Glyfosat"); the register names them
with qualifiers and salt/ester forms ("3-Jod-2-propynylbutylkarbamat (IPBC)",
"Glyfosat (isopropylaminsalt)"). Turning the former into stable CAS-based
ids is entity resolution, and doing it *honestly* means three tiers with
decreasing confidence and an explicit refusal to guess:

1. ``exact``     normalized-key match against a register substance.
2. ``qualifier`` match after stripping a trailing parenthetical qualifier
   the register appends ("(IPBC)", "(CAS Nr ...)"); same substance.
3. ``alias``     a hand-verified spelling variant (Swedish y/i, c/k, English
   endings) that denotes the same substance; the CAS still comes from the
   register, never asserted here.

Everything else stays ``provisional``: a name-based id, deliberately
unmatched. The large residual is the parent-acid-vs-salt problem (sales
reports the parent "Glyfosat"; the register lists each salt with its own
CAS). That is a chemical relationship, not a shared identity, and belongs in
the graph as edges, not forced here into a false match.
"""

from __future__ import annotations

from dataclasses import dataclass

from hazium.models import SalesRecord, Substance
from hazium.resolve.ids import substance_node_id

# Hand-verified spelling variants: sales-report name -> register name.
# Each pair denotes the same substance; the register supplies the CAS.
# Kept deliberately small; unverified pairs stay provisional.
_ALIASES: dict[str, str] = {
    "azoxystrobin": "azoxistrobin",  # English y / Swedish i
    "flonicamid": "flonikamid",  # English c / Swedish k
}


def normalize_name(name: str) -> str:
    """Collapse a substance name to a comparison key.

    Casefold and keep only alphanumerics, discarding spacing, hyphenation,
    and punctuation that vary freely between sources and PDF line wraps.
    """
    return "".join(ch for ch in name.casefold() if ch.isalnum())


def _strip_qualifier(name: str) -> str:
    """Drop a single trailing parenthetical, e.g. 'Foo (IPBC)' -> 'Foo'."""
    head, sep, _ = name.partition("(")
    return head.strip() if sep else name


@dataclass(frozen=True)
class Resolution:
    """The outcome of resolving one name."""

    substance_id: str
    cas_number: str | None
    method: str  # "exact" | "qualifier" | "alias" | "provisional"

    @property
    def matched(self) -> bool:
        return self.method != "provisional"


class SubstanceResolver:
    """Resolve free-text substance names against a register snapshot.

    Built once from the register's substance list, then queried per name.
    Index entries prefer CAS-bearing substances, so a name shared between a
    CAS-bearing and a CAS-less register entry resolves to the identified one.
    """

    def __init__(self, substances: list[Substance], aliases: dict[str, str] | None = None) -> None:
        self._by_key: dict[str, Substance] = {}
        self._by_qualifier_key: dict[str, Substance] = {}
        for substance in substances:
            self._register(self._by_key, normalize_name(substance.name), substance)
            stripped = _strip_qualifier(substance.name)
            if stripped != substance.name:
                self._register(self._by_qualifier_key, normalize_name(stripped), substance)
        self._aliases = {
            normalize_name(src): normalize_name(dst)
            for src, dst in (aliases if aliases is not None else _ALIASES).items()
        }

    @staticmethod
    def _register(index: dict[str, Substance], key: str, substance: Substance) -> None:
        """Insert, letting a CAS-bearing substance win over a CAS-less one."""
        existing = index.get(key)
        if existing is None or (existing.cas_number is None and substance.cas_number is not None):
            index[key] = substance

    def resolve(self, name: str) -> Resolution:
        """Resolve one substance name to a canonical id and provenance."""
        key = normalize_name(name)
        substance = self._by_key.get(key)
        if substance is not None:
            return self._hit(substance, "exact")

        qualifier_hit = self._by_qualifier_key.get(key)
        if qualifier_hit is not None:
            return self._hit(qualifier_hit, "qualifier")

        alias_target = self._aliases.get(key)
        if alias_target is not None and alias_target in self._by_key:
            return self._hit(self._by_key[alias_target], "alias")

        return Resolution(
            substance_id=substance_node_id(name=name),
            cas_number=None,
            method="provisional",
        )

    @staticmethod
    def _hit(substance: Substance, method: str) -> Resolution:
        return Resolution(
            substance_id=substance_node_id(
                cas_number=substance.cas_number,
                name=substance.name,
            ),
            cas_number=substance.cas_number,
            method=method,
        )


def resolve_sales_records(
    records: list[SalesRecord], resolver: SubstanceResolver
) -> list[SalesRecord]:
    """Remap ``SalesRecord.substance_id`` from its raw name-based id to the
    resolver's canonical (CAS-priority) id, where resolvable.

    ``SalesRecord.substance_id`` is built directly from the report's
    substance name at ingestion (``sources/kemi.py``, via
    ``substance_node_id(name=...)``), with no register cross-reference at
    that point -- entity resolution is this module's job, not the adapter's.
    Without this step, sales records never join to the graph's CAS-based
    substance ids and any feature or join keyed on ``substance_id`` silently
    sees zero sales for everyone. Records the resolver can't match keep their
    name-based id (inert -- it will never coincide with a real graph node
    id) rather than being dropped, matching the "provisional, not discarded"
    precedent set by ``Resolution`` itself.
    """
    resolved = []
    for record in records:
        name = record.substance_id.removeprefix("substance:name:").replace("-", " ")
        resolution = resolver.resolve(name)
        if resolution.matched:
            resolved.append(record.model_copy(update={"substance_id": resolution.substance_id}))
        else:
            resolved.append(record)
    return resolved
