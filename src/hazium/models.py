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
    NON_RENEWAL = "non_renewal"  # was approved, approval ended and was not renewed
    NON_APPROVAL = "non_approval"  # never approved (non-inclusion decision)
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

    A registration number is not unique: biocide product families share one.
    The register's stable per-named-product key is ``product_name_id``, and
    ``object_type`` distinguishes actual products (1) from regulatory objects
    (additional names, dispensations, parallel-trade permits).
    """

    registration_number: str
    product_name_id: int | None = Field(
        default=None, description="Stable per-named-product key; present for actual products"
    )
    object_type: int = Field(description="Register objektTypId; 1 == an actual product")
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
    hazard_class: str | None = Field(
        default=None, description="Paired CLP hazard class and category, e.g. 'Repr. 2'"
    )
    system: str = "CLP"
    atp: str | None = Field(
        default=None, description="Adaptation to Technical Progress that set this, e.g. 'ATP06'"
    )
    celex: str | None = Field(default=None, description="CELEX id of the adopting regulation")


class DegradationLink(Fact):
    """A substance's declared metabolic degradation to another substance.

    Both ids are resolved canonical node ids, not raw names: the source
    (e.g. EFSA OpenFoodTox) supplies authoritative CAS-based identity, so
    resolution happens at ingestion rather than being deferred to the graph
    builder, matching ``SalesRecord``/``HazardClassification``.
    """

    parent_substance_id: str
    metabolite_substance_id: str


class RegulatoryEvent(Fact):
    """A regulatory decision or process step concerning a substance."""

    substance_id: str
    kind: RegulatoryEventKind
    jurisdiction: str = Field(description="'EU' or ISO country code")
    event_date: date


class LiteratureVolumeRecord(Fact):
    """Annual scientific-literature volume for a substance, from Europe PMC.

    Two counts per (substance, year): ``total_hit_count`` (every paper
    mentioning the substance) and ``hazard_hit_count`` (the subset also
    matching a fixed hazard/toxicity term list). The *ratio*, ranked against
    the same-year population -- never the raw count alone, and never a
    self-relative trend across years -- is the feature signal. Verified
    2026-07-18 (DEV_LOG): raw hazard-hit counts rise for a genuine future EU
    non-renewal (Clothianidin) and for the project's own anchor negative
    (Fluazinam, never non-renewed) in the same direction; population-relative
    percentile, computed fresh at each cutoff, is what actually separates
    them (all 11 HEWB landmarks land at the 71st percentile or above a year
    or more before their real actions).

    ``known_at`` is Jan 1 of ``year + 1``: a calendar year's publication
    count is not complete/indexed until the year is over -- the same
    conservative-late convention ``eu_ppdb``'s non-renewal dating uses.
    """

    substance_id: str
    year: int
    hazard_hit_count: int
    total_hit_count: int


class MediaVolumeRecord(Fact):
    """Annual news-media attention for a substance, from the GDELT DOC 2.0 API.

    ``volume`` is GDELT's normalised coverage intensity (the share of all
    monitored global news matching the substance name), averaged over the
    calendar year. Normalised, not raw counts: it already compensates for the
    secular growth in total news volume, the same confound the literature
    feature has to correct for by hand, so it is directly comparable across
    years.

    **Coverage floor: GDELT DOC indexes from 2017-01-01** (verified 2026-07-19,
    live API). A substance's media attention before 2017 is simply not in this
    source, so any pre-2017 year is absent, not zero. This is a hard limit of
    the source, disclosed rather than papered over: for the historical HEWB
    landmarks (bans 2017-2021, public stories mostly 2008-2016) the pre-2017
    build-up is invisible here, which is why the site's public-controversy
    markers for the neonicotinoids (2012) and chlorpyrifos (2015) stay
    hand-curated. GDELT's real reach is the present-day watchlist and the
    2017+ tail, not the historical demo.

    Independent of the regulatory funnel and never used as a model *feature*
    (it would be a noisy, name-based echo); its role is a benchmark/comparison
    axis and a live present-day signal. ``known_at`` is Jan 1 of ``year + 1``,
    matching the literature feature's conservative-late convention.
    """

    substance_id: str
    year: int
    volume: float


class CLHIntentionRecord(Fact):
    """A substance's earliest ECHA CLH (harmonised classification) intention.

    The CLH process runs from an intention notification, through public
    consultation, to a RAC opinion, and only then is the harmonised
    classification enacted into CLP Annex VI (which `clp.py` already ingests,
    dated per ATP). The *intention* is the earliest dated point in that
    process, an in-funnel regulatory signal that precedes the Annex VI
    classification by roughly one to three years. It is exactly the kind of
    signal `SOURCE_ENHANCEMENT_SCOPE.md` Tier 2 scoped: earlier than the
    classification the model already sees, but firmly inside the regulatory
    funnel, so it is expected to help precision more than genuine early
    warning. Reported with inside-vs-outside-funnel SHAP so that distinction
    stays honest.

    ``intention_year`` is the year ECHA received the CLH dossier (the registry's
    bulk-filterable receipt date; the finer "date of intention" is a few months
    earlier and lives on per-substance detail pages). Only year granularity is
    kept, so ``known_at`` is conservatively Jan 1 of ``intention_year + 1`` (the
    same never-claim-it-earlier-than-provable convention the literature and
    media features use), since a receipt anywhere in the year is provably known
    by year end.

    Source acquisition is one-time and browser-assisted: ECHA's registry sits
    behind a WAF that refuses programmatic (Python) access, so this is parsed
    from a committed snapshot (`data/raw/clh_intentions_ppp.jsonl`), not fetched
    live. See DEV_LOG's HEWB v1.4 entry.
    """

    substance_id: str
    intention_year: int


class SourceDocument(Fact):
    """A document evidence can point to: EFSA conclusion, paper, article.

    ``subject_substance_id`` is optional: it captures the common case of one
    document assessing one substance (an EFSA conclusion), letting the graph
    builder emit the ``EVIDENCED_BY`` edge without re-deriving it. Documents
    with more complex or multiple subjects leave it unset and are linked by
    edges constructed elsewhere.
    """

    id: str
    title: str
    publisher: str
    url: str | None = None
    published_at: date | None = None
    subject_substance_id: str | None = None
