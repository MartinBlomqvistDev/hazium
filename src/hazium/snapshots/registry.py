"""The sources captured on a schedule, and why each one earns its place.

Policy, enforced by ``SourceSpec.future_use`` being required: a source is added
only with a concrete future use. An archive nobody queries is storage plus
maintenance plus schema drift, with no payoff.

**Not captured, and deliberately so:**

* **Anything on echa.europa.eu.** ECHA sits behind an Azure WAF that returns 403
  to programmatic clients (verified 2026-07-22 against the CLP Annex VI export).
  ECHA data therefore stays a manual browser acquisition, as
  ``echa_svhc_candidate_list.jsonl`` and ``clh_intentions_ppp.jsonl`` already
  are. A collector that silently 403s every month is worse than no collector.
* **Europe PMC and GDELT.** Both are per-substance query APIs rather than bulk
  registers, and ``pipeline/14`` and ``pipeline/17`` already fetch them with
  correct dating. Re-capturing them here would duplicate that.
"""

from __future__ import annotations

from hazium.snapshots.models import Cadence, CollectorKind, SourceSpec

EU_PPDB_DETAILS = SourceSpec(
    name="eu_ppdb_details",
    description=(
        "EU Pesticides Database per-substance details (approval, expiry, "
        "classification, toxicology, legislations, authorisations)."
    ),
    future_use=(
        "Supplies the missing dates for Candidate-for-Substitution status, ADI, "
        "and classification, which the bulk export publishes undated and which "
        "were rejected as features for exactly that reason (Tier 0a, DEV_LOG "
        "2026-07-18). Month-over-month diffs date every change from now on."
    ),
    cadence=Cadence.MONTHLY,
    kind=CollectorKind.PPDB_DETAILS,
    url=(
        "https://ec.europa.eu/food/plant/pesticides/eu-pesticides-database/"
        "backend/api/active_substance/details"
    ),
    # Highest id observed in the bulk export is 1577 (2026-07), and 38 real
    # substances sit above 1500, so a cap at the current maximum silently drops
    # whatever is registered next. Scanned with headroom; misses are cheap.
    params={"id_start": 1, "id_end": 1800},
)

SGU_GROUNDWATER = SourceSpec(
    name="sgu_groundwater",
    description=(
        "SGU groundwater chemistry analyses (Grundvattenkvalitet), one record "
        "per measured parameter per sampling occasion, CAS-coded."
    ),
    future_use=(
        "The fluazinam/TFA gap-closer. SGU's PFAS and TFA groundwater results "
        "are 2023-2025, after every HEWB cutoff, so they can only serve as "
        "post-hoc validation today. Captured forward they become a legitimate "
        "pre-cutoff environmental feature for cutoffs from roughly 2029. Every "
        "record carries cas_kod, so it joins the graph directly."
    ),
    cadence=Cadence.MONTHLY,
    kind=CollectorKind.OGC_FEATURES_WINDOW,
    url=(
        "https://api.sgu.se/oppnadata/"
        "grundvattenkvalitet-analysresultat-provplatser-v2/ogc/features/v1"
    ),
    params={
        "collection": "analysresultat",
        "date_field": "provtagningsdatum",
        "page_size": 1000,
        # 9 of 90 properties. Everything needed to join a measurement to a
        # substance, place it in time, and read its value with its detection
        # limits. The other 81 are administrative and would multiply the
        # archive by roughly ten for no join value.
        "fields": (
            "provplatsuuid,provtagningsdatum,cas_kod,parameternamn,"
            "matvardetal,enhet,loq,lod,lanskod"
        ),
    },
)

KEMI_SALES = SourceSpec(
    name="kemi_sales",
    description="Kemikalieinspektionen annual pesticide and biocide sales report (PDF).",
    future_use=(
        "Extends the sales time series as each year is published. The existing "
        "adapter already stamps figures with the report's publication date; "
        "capturing the report itself means a missed publication cannot create a "
        "silent gap."
    ),
    cadence=Cadence.ANNUAL,
    kind=CollectorKind.FILE,
    url=(
        "https://www.kemi.se/webdav/files/Kemikaliestatistik/"
        "Bek%C3%A4mpningsmedel/forsalda_bkm_2024.pdf"
    ),
)

ZENODO_OPENFOODTOX = SourceSpec(
    name="zenodo_openfoodtox",
    description="Zenodo record metadata for the EFSA OpenFoodTox export.",
    future_use=(
        "Detects new OpenFoodTox releases. The payload is metadata only, a few "
        "kilobytes, so a monthly check is nearly free; a changed digest is the "
        "signal to re-ingest the full export."
    ),
    cadence=Cadence.MONTHLY,
    kind=CollectorKind.FILE,
    url="https://zenodo.org/api/records/5076033",
)

#: Every source captured, in the order a full run walks them.
REGISTRY: tuple[SourceSpec, ...] = (
    EU_PPDB_DETAILS,
    SGU_GROUNDWATER,
    KEMI_SALES,
    ZENODO_OPENFOODTOX,
)


def spec_by_name(name: str) -> SourceSpec:
    """Look up a source spec.

    Args:
        name: ``SourceSpec.name``.

    Returns:
        The matching spec.

    Raises:
        KeyError: If no source with that name is registered, listing the
            available names so a typo is immediately obvious.
    """
    for spec in REGISTRY:
        if spec.name == name:
            return spec
    known = ", ".join(s.name for s in REGISTRY)
    raise KeyError(f"unknown source {name!r}; registered: {known}")
