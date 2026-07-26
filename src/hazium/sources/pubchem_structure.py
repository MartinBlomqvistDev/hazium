"""Adapter for PubChem molecular structure, keyed by CAS.

Every other source in this project is dated, because every other source is an
assertion someone made on a day. A molecular structure is not. Fluazinam
contained six fluorine atoms in 2009 and contains six today, and it would have
contained six had nobody looked. That makes structure the only feature class
here that cannot leak: there is no cutoff at which it was not knowable, so no
`known_at` discipline applies and none is faked.

It also sits as far outside the regulatory funnel as a feature can. EFSA
assessment counts and CLH intentions read the regulator's own pipeline; a
formula reads the molecule.

Why this exists: HEWB predicts EU withdrawal, and the hazard that motivated the
project is a degradation product. Fluazinam breaks down to trifluoroacetic acid
(TFA), a persistent PFAS that reaches groundwater, and the parent substance's
own regulatory record never mentions it. No amount of regulatory evidence
carries that fact. The molecule does: TFA comes from trifluoromethyl groups, and
a CF3 group is visible in a SMILES string.

PubChem's PUG REST interface is public, unauthenticated and rate-limited to
about five requests a second. Responses are cached to a committed JSONL so the
screen reruns offline and so a reviewer can check exactly which structure was
used, rather than trusting whatever PubChem returns next year.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

SOURCE = "pubchem:pug-rest"

#: PubChem asks for no more than five requests a second from unauthenticated
#: clients. This is the polite side of that.
REQUEST_DELAY_SECONDS = 0.22

_PUG = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound"
_USER_AGENT = "hazium/0.1 (research; github.com/MartinBlomqvistDev/hazium)"

#: The ways PubChem writes a trifluoromethyl group in a SMILES string. Matching
#: on text rather than with a chemistry toolkit is a deliberate trade: CF3 is an
#: unambiguous motif with a small, enumerable set of spellings, and carrying
#: RDKit into CI to recognise it would cost more than it settles. The
#: `fluorine_count` cross-check below is what catches a spelling we missed.
CF3_PATTERNS: tuple[str, ...] = (
    "C(F)(F)F",
    "FC(F)(F)",
    "C(F)(F)(F)",
    "(F)(F)F",
)

#: Fluorine in a molecular formula: "F" followed by an optional count, but not
#: "Fe". Formulas are Hill notation, so a lowercase letter after F means a
#: different element.
_FLUORINE = re.compile(r"F(?![a-z])(\d*)")


class StructureRecord(BaseModel):
    """A molecule's composition, as PubChem reports it.

    Deliberately not a `Fact`: it carries no ``known_at`` because there is no
    date on which a molecule started having its formula. Anything downstream
    that wants to place this in time should treat it as knowable at every
    cutoff, which is what `screen/tfa.py` does.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    substance_id: str = Field(description="Canonical id, e.g. 'substance:cas:79622-59-6'")
    cas: str
    molecular_formula: str | None = None
    smiles: str | None = None
    pubchem_cid: int | None = None
    resolved: bool = Field(description="False when PubChem has no record for this CAS")

    @property
    def fluorine_count(self) -> int:
        """Fluorine atoms per molecule, from the Hill-notation formula."""
        if not self.molecular_formula:
            return 0
        match = _FLUORINE.search(self.molecular_formula)
        if not match:
            return 0
        return int(match.group(1) or 1)

    @property
    def cf3_groups(self) -> int:
        """How many trifluoromethyl groups the SMILES string spells out.

        Counted rather than flagged because TFA yield scales with how many CF3
        groups a molecule carries, and because a count makes a miscount visible
        against ``fluorine_count``.
        """
        if not self.smiles:
            return 0
        best = 0
        for pattern in CF3_PATTERNS:
            best = max(best, self.smiles.count(pattern))
        return best

    @property
    def has_cf3(self) -> bool:
        return self.cf3_groups > 0

    @property
    def unexplained_fluorine(self) -> bool:
        """Three or more fluorines but no CF3 matched.

        Either the molecule carries fluorine in some other arrangement, which is
        a real and uninteresting case, or `CF3_PATTERNS` missed a spelling,
        which is a bug. The screen reports these separately rather than
        silently treating them as negatives.
        """
        return self.fluorine_count >= 3 and not self.has_cf3


def _get(path: str) -> dict | None:
    request = urllib.request.Request(f"{_PUG}/{path}", headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def fetch_structure(substance_id: str, name: str | None = None) -> StructureRecord:
    """Look a substance up in PubChem by CAS, falling back to its name.

    CAS is tried first because it is unambiguous. The name fallback exists for
    the handful of register entries whose CAS PubChem does not index, and it is
    the weaker of the two: a name can resolve to a salt or an isomer of what was
    meant. Callers that care should check ``cas`` against the returned record.
    """
    cas = substance_id.removeprefix("substance:cas:")
    payload = None
    if substance_id.startswith("substance:cas:"):
        payload = _get(f"name/{urllib.parse.quote(cas)}/property/MolecularFormula,SMILES/JSON")
    if payload is None and name:
        payload = _get(f"name/{urllib.parse.quote(name)}/property/MolecularFormula,SMILES/JSON")
    if payload is None:
        return StructureRecord(substance_id=substance_id, cas=cas, resolved=False)

    row = payload["PropertyTable"]["Properties"][0]
    return StructureRecord(
        substance_id=substance_id,
        cas=cas,
        molecular_formula=row.get("MolecularFormula"),
        smiles=row.get("SMILES") or row.get("ConnectivitySMILES"),
        pubchem_cid=row.get("CID"),
        resolved=bool(row.get("MolecularFormula")),
    )


def fetch_all(
    substances: Iterable[tuple[str, str]], known: dict[str, StructureRecord] | None = None
) -> list[StructureRecord]:
    """Fetch structures for ``(substance_id, name)`` pairs, reusing ``known``.

    Structures do not change, so anything already resolved is never re-fetched.
    Unresolved entries are retried, since a PubChem miss can be a transient 404
    on a name that later gets indexed.
    """
    cache = dict(known or {})
    out: list[StructureRecord] = []
    for substance_id, name in substances:
        cached = cache.get(substance_id)
        if cached is not None and cached.resolved:
            out.append(cached)
            continue
        record = fetch_structure(substance_id, name)
        time.sleep(REQUEST_DELAY_SECONDS)
        cache[substance_id] = record
        out.append(record)
    return out


def load_structures(path: Path) -> dict[str, StructureRecord]:
    """Read a structure cache written by `write_structures`."""
    if not path.exists():
        return {}
    records: dict[str, StructureRecord] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = StructureRecord.model_validate_json(line)
            records[record.substance_id] = record
    return records


def write_structures(path: Path, records: Iterable[StructureRecord]) -> int:
    """Write the structure cache, sorted so the diff is stable between runs."""
    ordered = sorted(records, key=lambda r: r.substance_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for record in ordered:
            f.write(record.model_dump_json() + "\n")
    return len(ordered)
