"""Run the TFA-precursor screen and check it against two held-out confirmations.

The screen itself is one rule: an approved substance carrying a trifluoromethyl
group can form TFA. What makes it a result rather than an assertion is that two
independent bodies have said which substances do, and neither list is an input.

Kemikalieinspektionen named six on 2025-11-20. EFSA's own degradation records
name three more. If the rule is doing anything, it flags them; if it flags them
by flagging most of the population, it is doing nothing, so the chance baseline
is reported next to the hit count and never without it.

Usage:
    python pipeline/35_run_tfa_screen.py
    python pipeline/35_run_tfa_screen.py --top 15
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from math import comb
from pathlib import Path

from hazium.screen.tfa import (
    EFSA_CONFIRMED_TFA_PARENTS,
    EXPOSURE_CAP_TONNES,
    KEMI_TFA_COHORT,
    screen,
)
from hazium.models import SalesRecord, Substance
from hazium.sources.kemi_uses import crops_grown
from hazium.resolve.names import SubstanceResolver, resolve_sales_records
from hazium.sources.pubchem_structure import load_structures

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"
STRUCTURES = ROOT / "data" / "raw" / "pubchem_structures.jsonl"

#: KEMI register codes, matching `pipeline/25`.
PLANT_PROTECTION = "Växtskyddsmedel"
ACTUAL_PRODUCT = 1
OUT_CSV = PROCESSED / "tfa_screen.csv"
SITE_DATA = ROOT / "web" / "data" / "tfa_screen.json"


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"missing {path}; run the pipeline that writes it first")
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _load(path: Path, model):
    with path.open(encoding="utf-8") as f:
        return [model.model_validate_json(line) for line in f]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--watchlist", type=Path, default=PROCESSED / "survival_watchlist_h3.csv")
    parser.add_argument("--top", type=int, default=30, help="rows to print")
    args = parser.parse_args()

    rows = _read_csv(args.watchlist)
    population = {r["substance_id"] for r in rows}
    names = {r["substance_id"]: r["name"] for r in rows}

    structures = {sid: rec for sid, rec in load_structures(STRUCTURES).items() if sid in population}
    if not structures:
        raise SystemExit("no structures for this population; run pipeline/34 first")

    # Exposure is read from KEMI's sales file for the whole population, not from
    # the site's watchlist export. That export is the top 100 of a different
    # ranking, and most substances this screen flags are not in it, so sourcing
    # tonnage there left the exposure half of the rule almost entirely empty.
    sales = resolve_sales_records(
        _load(PROCESSED / "kemi_sales.jsonl", SalesRecord),
        SubstanceResolver(_load(PROCESSED / "kemi_register_substances.jsonl", Substance)),
    )
    latest = max(s.year for s in sales)
    tonnes: dict[str, float] = {}
    for record in sales:
        if record.year != latest or record.tonnes_active_substance is None:
            continue
        tonnes[record.substance_id] = (
            tonnes.get(record.substance_id, 0.0) + record.tonnes_active_substance
        )

    # Crops are read from KEMI's product register for the whole population, for
    # the same reason as tonnage: `crop_exposure_*_by_substance.csv` only covers
    # the watchlist's top 100, and most substances this screen flags are not in
    # it, so joining there left real crop uses looking like absent ones.
    products = [
        json.loads(line)
        for line in (PROCESSED / "kemi_register_products.jsonl").open(encoding="utf-8")
    ]
    crops: dict[str, list[str]] = {}
    for product in products:
        if not (
            product.get("main_group") == PLANT_PROTECTION
            and product.get("object_type") == ACTUAL_PRODUCT
            and product.get("approved")
        ):
            continue
        grown = crops_grown(product.get("usage_areas") or [])
        if not grown:
            continue
        for ingredient in product.get("ingredients") or []:
            cas = (ingredient.get("cas_number") or "").strip()
            if not cas:
                continue
            sid = f"substance:cas:{cas}"
            crops.setdefault(sid, [])
            for crop in grown:
                if crop not in crops[sid]:
                    crops[sid].append(crop)
    for value in crops.values():
        value.sort()

    result = screen(structures, names, tonnes=tonnes, crops=crops)

    print(f"approved population screened: {result.population}")
    print(
        f"structures PubChem could not resolve: {result.unresolved} (excluded, not assumed clean)"
    )
    print(
        f"flagged as TFA precursors: {result.flagged_count} "
        f"({result.flagged_count / result.population:.1%})\n"
    )

    print(f"top {min(args.top, result.flagged_count)} by fluorine payload and Swedish exposure")
    print(f"  {'#':>3} {'substance':<28}{'formula':<24}{'CF3':>4}{'t/yr':>8}  flag")
    print("  " + "-" * 78)
    for rank, entry in enumerate(result.flagged[: args.top], start=1):
        mark = ""
        if entry.in_kemi_cohort:
            mark = "KEMI reevaluation"
        elif entry.efsa_confirmed:
            mark = "EFSA: forms TFA"
        volume = f"{entry.tonnes:.1f}" if entry.tonnes else "-"
        print(
            f"  {rank:>3} {entry.name[:27]:<28}{(entry.molecular_formula or '')[:23]:<24}"
            f"{entry.cf3_groups:>4}{volume:>8}  {mark}"
        )

    # --- held-out check 1: the regulator's own list -------------------------
    print("\nCHECK 1: the six KEMI opened for reevaluation on 2025-11-20")
    for sid, label in sorted(KEMI_TFA_COHORT.items(), key=lambda kv: kv[1]):
        hit = next((e for e in result.flagged if e.substance_id == sid), None)
        where = f"flagged, rank {result.flagged.index(hit) + 1}" if hit else "MISSED"
        in_pop = "" if sid in structures else "  (not in the approved population)"
        print(f"   {label:<24}{where}{in_pop}")
    print(
        f"\n   found {result.kemi_found} of {result.kemi_total}; a same-sized random draw "
        f"would find {result.expected_kemi_by_chance:.1f}"
    )
    if result.kemi_found == result.kemi_total and result.flagged_count < result.population:
        p = comb(result.flagged_count, result.kemi_total) / comb(
            result.population, result.kemi_total
        )
        print(f"   probability of that by chance: {p:.2e}  (1 in {1 / p:,.0f})")

    # --- held-out check 2: EFSA's own degradation records -------------------
    print("\nCHECK 2: substances EFSA's degradation records already link to TFA")
    for sid in sorted(EFSA_CONFIRMED_TFA_PARENTS):
        hit = next((e for e in result.flagged if e.substance_id == sid), None)
        if sid not in structures:
            print(f"   {sid:<34}not in the approved population")
        else:
            print(f"   {names.get(sid, sid):<34}{'flagged' if hit else 'MISSED'}")

    if result.unexplained_fluorine:
        print(
            f"\n{len(result.unexplained_fluorine)} substances carry 3+ fluorines with no CF3 "
            "matched. Not necessarily wrong, but worth an eye."
        )

    # --- outputs ------------------------------------------------------------
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "rank",
                "substance_id",
                "name",
                "molecular_formula",
                "fluorine_count",
                "cf3_groups",
                "tonnes",
                "score",
                "in_kemi_cohort",
                "efsa_confirmed",
                "crops",
            ]
        )
        for rank, e in enumerate(result.flagged, start=1):
            writer.writerow(
                [
                    rank,
                    e.substance_id,
                    e.name,
                    e.molecular_formula,
                    e.fluorine_count,
                    e.cf3_groups,
                    "" if e.tonnes is None else e.tonnes,
                    e.score,
                    e.in_kemi_cohort,
                    e.efsa_confirmed,
                    "; ".join(e.crops),
                ]
            )

    payload = {
        "generated": date.today().isoformat(),
        "population": result.population,
        "unresolved": result.unresolved,
        "flagged": result.flagged_count,
        "kemi_found": result.kemi_found,
        "kemi_total": result.kemi_total,
        "expected_by_chance": round(result.expected_kemi_by_chance, 2),
        "efsa_found": result.efsa_found,
        "efsa_total": len(EFSA_CONFIRMED_TFA_PARENTS & set(structures)),
        "exposure_cap_tonnes": EXPOSURE_CAP_TONNES,
        # Fluorine-bearing but not CF3, almost all difluoromethyl. Published so
        # the site states the exclusion from the run rather than from memory.
        "fluorine_without_cf3": len(result.unexplained_fluorine),
        "entries": [
            {
                "rank": rank,
                "name": e.name,
                "cas": e.substance_id.removeprefix("substance:cas:"),
                "formula": e.molecular_formula,
                "fluorine_count": e.fluorine_count,
                "cf3_groups": e.cf3_groups,
                "tonnes": e.tonnes,
                "crops": list(e.crops),
                "score": e.score,
                "in_kemi_cohort": e.in_kemi_cohort,
                "efsa_confirmed": e.efsa_confirmed,
            }
            for rank, e in enumerate(result.flagged, start=1)
        ],
    }
    SITE_DATA.parent.mkdir(parents=True, exist_ok=True)
    SITE_DATA.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")

    print(f"\nwrote {OUT_CSV.relative_to(ROOT)}")
    print(f"wrote {SITE_DATA.relative_to(ROOT)} ({SITE_DATA.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
