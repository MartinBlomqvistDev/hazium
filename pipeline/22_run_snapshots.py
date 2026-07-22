"""Capture dated snapshots of current-state-only sources.

I/O boundary for ``hazium.snapshots``. Run on a schedule (see
``.github/workflows/snapshots.yml``); every capture is stamped with the date it
was taken, and that date is the ``known_at`` of anything later derived from it.

Usage::

    python pipeline/22_run_snapshots.py --list
    python pipeline/22_run_snapshots.py --all
    python pipeline/22_run_snapshots.py --source sgu_groundwater
    python pipeline/22_run_snapshots.py --source eu_ppdb_details --id-end 50

Exit status is 0 when the run is healthy, including when a single source fails
transiently, and 1 when every source failed or some source has failed
persistently enough to be considered broken.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hazium.snapshots.models import SourceSpec
from hazium.snapshots.registry import REGISTRY, spec_by_name
from hazium.snapshots.runner import broken_sources, exit_code, run_sources
from hazium.snapshots.store import SnapshotStore

DEFAULT_ROOT = Path("data/snapshots")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="Snapshot store root")
    parser.add_argument("--source", action="append", default=[], help="Source name (repeatable)")
    parser.add_argument("--all", action="store_true", help="Capture every registered source")
    parser.add_argument("--list", action="store_true", help="List sources and exit")
    parser.add_argument(
        "--id-end",
        type=int,
        default=None,
        help="Override the EU PPDB id scan upper bound (useful for a quick check)",
    )
    return parser.parse_args(argv)


def _list_sources() -> None:
    print(f"{len(REGISTRY)} registered sources\n")
    for spec in REGISTRY:
        print(f"  {spec.name}  [{spec.cadence.value}, {spec.kind.value}]")
        print(f"    {spec.description}")
        print(f"    future use: {spec.future_use}\n")


def _selected(args: argparse.Namespace) -> list[SourceSpec]:
    if args.all:
        return list(REGISTRY)
    return [spec_by_name(name) for name in args.source]


def _apply_overrides(specs: list[SourceSpec], args: argparse.Namespace) -> list[SourceSpec]:
    """Apply CLI overrides, returning new frozen specs."""
    if args.id_end is None:
        return specs
    out = []
    for spec in specs:
        if "id_end" in spec.params:
            params = dict(spec.params) | {"id_end": args.id_end}
            out.append(spec.model_copy(update={"params": params}))
        else:
            out.append(spec)
    return out


def _report(report, store: SnapshotStore, specs: list[SourceSpec]) -> None:
    print(f"\ncaptured {len(report.succeeded)}/{len(report.observations)} sources")
    for obs in report.observations:
        if not obs.ok:
            print(f"  [FAIL] {obs.source}: {obs.error}")
            continue
        state = "unchanged" if obs.unchanged else "NEW"
        size_kb = (obs.n_bytes or 0) / 1024
        detail = ", ".join(f"{k}={v}" for k, v in obs.meta.items() if k != "url")
        print(f"  [{state:9s}] {obs.source}  {size_kb:,.1f} KiB  {detail}")

    broken = broken_sources(store, specs)
    if broken:
        print(f"\nBROKEN (failed >= 3 runs in a row): {', '.join(broken)}")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.list:
        _list_sources()
        return 0

    specs = _apply_overrides(_selected(args), args)
    if not specs:
        print("nothing to do: pass --all, --source NAME, or --list", file=sys.stderr)
        return 2

    store = SnapshotStore(args.root)
    print(f"store: {store.root.resolve()}")
    print(f"capturing: {', '.join(s.name for s in specs)}")

    report = run_sources(specs, store)
    _report(report, store, specs)
    return exit_code(report, store, specs)


if __name__ == "__main__":
    raise SystemExit(main())
