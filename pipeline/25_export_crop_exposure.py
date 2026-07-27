"""Map the forward watchlist onto the Swedish crops it is actually used on.

Everything else here ranks substances. A substance rank is not legible to
anyone outside the field: "potato" and "winter wheat" are. This joins the
current watchlist to KemI's approved product register and reads the crop out of
each product's free-text usage areas, so the model's live ranking can be stated
as an exposure map rather than a list of names.

**Why the watchlist and not a historical cutoff.** Joining a past ranking to
today's market looks obvious and is wrong. A market can only contain substances
that are still approved, so everything the model correctly flagged and that was
subsequently banned has already left the shelves. Measured directly at the
2023-01-01 cutoff, 15 of the top 50 were still sold in Sweden and every one of
them was a true negative, while all three top-50 substances that were actually
banned were gone. The join selects for the model's false positives by
construction. `pipeline/13` avoids this because it scores today's population,
from which realised outcomes are already censored.

**What this output is not.** These are substances the model currently ranks as
concerning. Nothing here has been checked against a future that has not
happened. Report it as a dated, falsifiable watchlist, never as a prediction
that a named product will be withdrawn, and never attached to a brand: at an
average precision of 0.254 most of these will not be actioned, and putting
named commercial products on a mostly-wrong list is both unfair and legally
exposed.

Usage:
    python pipeline/25_export_crop_exposure.py
    python pipeline/25_export_crop_exposure.py --variant early_warning --top 100
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from hazium.sources.kemi_uses import crops_grown

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"

#: Set by --watchlist so the survival ranking can be used in place of pipeline/13.
WATCHLIST_PATH: Path | None = None

#: KemI's own grouping for plant protection products, as printed in the register.
PLANT_PROTECTION = "Växtskyddsmedel"

#: Register objektTypId 1 is an actual product. The other values are regulatory
#: objects (additional names, dispensations, parallel-trade permits) that would
#: double-count the same physical product.
ACTUAL_PRODUCT = 1


def load_watchlist(variant: str, top: int) -> dict[str, tuple[int, str]]:
    """Read the top-N rows of a watchlist export.

    Args:
        variant: ``headline`` or ``early_warning``.
        top: How many ranks to keep.

    Returns:
        Substance id -> (rank, name).
    """
    path = WATCHLIST_PATH or PROCESSED / f"current_watchlist_{variant}.csv"
    if not path.exists():
        raise SystemExit(f"missing {path}; run pipeline/13 or pipeline/30 first")
    out: dict[str, tuple[int, str]] = {}
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            rank = int(row["rank"])
            if rank > top:
                break
            out[row["substance_id"]] = (rank, row["name"])
    return out


def load_approved_products() -> list[dict]:
    """Currently approved Swedish plant protection products, one row each."""
    path = PROCESSED / "kemi_register_products.jsonl"
    with path.open(encoding="utf-8") as f:
        rows = [json.loads(line) for line in f]
    return [
        r
        for r in rows
        if r.get("main_group") == PLANT_PROTECTION
        and r.get("object_type") == ACTUAL_PRODUCT
        and r.get("approved")
    ]


def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", default="headline", choices=("headline", "early_warning"))
    parser.add_argument(
        "--top",
        type=int,
        default=100,
        help=(
            "watchlist ranks to include. 100 rather than 50: at cutoffs old "
            "enough to have resolved, precision holds a plateau to about k=50 "
            "(0.68-0.78) and is still 0.57-0.62 at k=100, while recall roughly "
            "doubles. An exposure map wants the coverage."
        ),
    )
    parser.add_argument(
        "--watchlist",
        type=Path,
        default=None,
        help="watchlist CSV to read; defaults to pipeline/13's output",
    )
    args = parser.parse_args()
    global WATCHLIST_PATH
    WATCHLIST_PATH = args.watchlist

    watchlist = load_watchlist(args.variant, args.top)
    products = load_approved_products()
    print(f"watchlist top {args.top}: {len(watchlist)} substances")
    print(f"approved Swedish plant protection products: {len(products)}")

    # crop -> products approved for it, and the subset carrying a watchlist substance
    crop_products: dict[str, set[str]] = defaultdict(set)
    crop_flagged: dict[str, set[str]] = defaultdict(set)
    crop_substances: dict[str, set[str]] = defaultdict(set)
    flagged_products: set[str] = set()
    substance_crops: dict[str, set[str]] = defaultdict(set)

    for product in products:
        key = str(product.get("product_name_id") or product.get("registration_number"))
        areas = product.get("usage_areas") or []
        if not isinstance(areas, list):
            areas = [areas]
        crops = crops_grown([str(a) for a in areas])
        if not crops:
            continue

        hits = {
            watchlist[sid]
            for ing in (product.get("ingredients") or [])
            if (cas := ing.get("cas_number"))
            and (sid := f"substance:cas:{cas.strip()}") in watchlist
        }
        if hits:
            flagged_products.add(key)
        for crop in crops:
            crop_products[crop].add(key)
            for _rank, name in hits:
                crop_flagged[crop].add(key)
                crop_substances[crop].add(name)
                substance_crops[name].add(crop)

    rows = []
    for crop, prods in sorted(crop_products.items(), key=lambda kv: -len(kv[1])):
        flagged = crop_flagged.get(crop, set())
        rows.append(
            [
                crop,
                len(prods),
                len(flagged),
                f"{len(flagged) / len(prods) * 100:.0f}",
                "; ".join(sorted(crop_substances.get(crop, ()))),
            ]
        )
    out = PROCESSED / f"crop_exposure_{args.variant}.csv"
    _write_csv(
        out,
        ["crop", "approved_products", "products_with_watchlist_substance", "percent", "substances"],
        rows,
    )

    detail = PROCESSED / f"crop_exposure_{args.variant}_by_substance.csv"
    _write_csv(
        detail,
        ["rank", "substance", "crops"],
        [
            [rank, name, "; ".join(sorted(substance_crops[name]))]
            for _sid, (rank, name) in sorted(watchlist.items(), key=lambda kv: kv[1][0])
            if name in substance_crops
        ],
    )

    # Population totals, written out because they cannot be recovered from the
    # per-crop table: a product approved for wheat, barley and rye appears in
    # three rows, so summing the columns counts it three times. Anything using
    # the per-crop shares needs a real denominator to compare them against.
    with_crop = len({p for s in crop_products.values() for p in s})
    summary = PROCESSED / f"crop_exposure_{args.variant}_summary.csv"
    _write_csv(
        summary,
        ["approved_products", "products_with_a_crop", "products_with_watchlist_substance"],
        [[len(products), with_crop, len(flagged_products)]],
    )

    on_market = len(set(substance_crops))
    print(f"\nwatchlist substances found in an approved Swedish product: {on_market}")
    print(f"products carrying one: {len(flagged_products)}")
    print(f"\n{'crop':<24} {'products':>9} {'flagged':>8} {'share':>7}")
    print("-" * 52)
    for row in rows[:15]:
        print(f"{row[0]:<24} {row[1]:>9} {row[2]:>8} {row[3]:>6}%")
    print(f"\nwrote {out}")
    print(f"wrote {detail}")
    print(f"wrote {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
