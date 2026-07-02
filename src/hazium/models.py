"""Data contracts for the Hazium knowledge graph.

Every fact crossing a boundary is a frozen Pydantic model carrying provenance
(``source``) and temporal validity (``known_at``). Facts are immutable:
corrections are new facts, never mutations.

``known_at`` is the earliest date the fact was publicly knowable. All
retrospective evaluation filters on it; see ``TemporalGraph.as_of``.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

AttrValue = str | int | float


class NodeType(StrEnum):
    """Entity types in the knowledge graph."""

    SUBSTANCE = "substance"
    PRODUCT = "product"
    CROP = "crop"
    COUNTRY = "country"
    HAZARD = "hazard"
    DOCUMENT = "document"
    REGULATORY_EVENT = "regulatory_event"


class EdgeType(StrEnum):
    """Relationship types.

    A metabolite is a substance: degradation is an edge between substances,
    not a node type. This keeps cross-domain bridges (fluazinam -> TFA -> PFAS)
    first-class.
    """

    CONTAINS = "contains"  # product -> substance
    DEGRADES_TO = "degrades_to"  # substance -> substance
    APPROVED_IN = "approved_in"  # substance -> country
    USED_ON = "used_on"  # product -> crop
    CLASSIFIED_AS = "classified_as"  # substance -> hazard
    DETECTED_IN = "detected_in"  # substance -> crop
    SUBJECT_OF = "subject_of"  # substance -> regulatory_event
    EVIDENCED_BY = "evidenced_by"  # any -> document


class Fact(BaseModel):
    """Base class for anything asserted by a source at a point in time."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str = Field(description="Source identifier, e.g. 'kemi:sales:2025'")
    known_at: date = Field(description="Earliest date this fact was publicly knowable")


class Node(Fact):
    """A graph entity."""

    id: str = Field(description="Canonical id, e.g. 'substance:cas:79622-59-6'")
    type: NodeType
    label: str
    attrs: dict[str, AttrValue] = Field(default_factory=dict)


class Edge(Fact):
    """A directed, typed, temporally-anchored relationship."""

    subject: str
    predicate: EdgeType
    object: str
    attrs: dict[str, AttrValue] = Field(default_factory=dict)


class RegulatoryEventKind(StrEnum):
    APPROVAL = "approval"
    RENEWAL = "renewal"
    WITHDRAWAL = "withdrawal"
    RESTRICTION = "restriction"
    REEVALUATION_STARTED = "reevaluation_started"


class Substance(Fact):
    """Identity card for a chemical substance.

    Identifiers come from existing vocabularies (CAS, EC, PubChem); Hazium
    never mints its own chemistry identifiers.
    """

    name: str
    cas_number: str | None = None
    ec_number: str | None = None
    pubchem_cid: int | None = None


class ProductIngredient(BaseModel):
    """One active substance in a registered product, as declared."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    cas_number: str | None = None
    concentration: str | None = Field(default=None, description="As printed, e.g. '500 g/L'")


class ProductRegistration(Fact):
    """A product's registration state in a national register, at snapshot time.

    Registers are live databases without publication history, so ``known_at``
    is the snapshot date: the fact was publicly knowable at least by then.
    """

    registration_number: str
    name: str
    country: str = Field(description="ISO 3166-1 alpha-2, e.g. 'SE'")
    main_group: str = Field(description="e.g. 'Växtskyddsmedel'")
    approved: bool
    previously_approved: bool
    usage_ban: bool
    approval_expires: date | None = None
    ingredients: tuple[ProductIngredient, ...] = ()
    usage_areas: tuple[str, ...] = ()


class SalesRecord(Fact):
    """Annual sales of an active substance in one country."""

    substance_id: str
    country: str = Field(description="ISO 3166-1 alpha-2, e.g. 'SE'")
    year: int
    tonnes_active_substance: float


class HazardClassification(Fact):
    """A hazard classification of a substance, e.g. CLP H-statements."""

    substance_id: str
    hazard_code: str = Field(description="e.g. 'H351'")
    system: str = "CLP"


class RegulatoryEvent(Fact):
    """A regulatory decision or process step concerning a substance."""

    substance_id: str
    kind: RegulatoryEventKind
    jurisdiction: str = Field(description="'EU' or ISO country code")
    event_date: date


class SourceDocument(Fact):
    """A document evidence can point to: EFSA conclusion, paper, article."""

    id: str
    title: str
    publisher: str
    url: str | None = None
    published_at: date | None = None
