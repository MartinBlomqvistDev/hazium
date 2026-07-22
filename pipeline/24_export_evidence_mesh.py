"""Export a two-hop evidence mesh with a precomputed 3D layout, for the site.

I/O boundary for ``graph.timeline.build_evidence_mesh`` and
``graph.layout3d.force_layout_3d``. The layout is computed here rather than in
the browser so the picture is identical on every build and reviewable in a diff;
a client-side simulation would settle differently on every load.

**Size is the reason this defaults to one case.** A mesh is roughly 600 nodes and
1,200 edges, about 40 KiB once compacted. Exporting all eleven landmarks would
put ~450 KiB of JSON in the page bundle for a visual that shows one substance at
a time. Pass ``--case`` to add more and accept the weight knowingly.

Usage:
    python pipeline/24_export_evidence_mesh.py
    python pipeline/24_export_evidence_mesh.py --case Clothianidin --case Mancozeb
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from hazium.benchmark.hewb import ANNUAL_CUTOFFS, LANDMARK_CASES
from hazium.graph.build import load_graph
from hazium.graph.layout3d import force_layout_3d, layout_quality
from hazium.graph.timeline import build_evidence_mesh
from hazium.sources.clp import CLP_REGULATION_URL, hazard_class_by_code, load as load_clp

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"
SITE_DATA = ROOT / "web" / "data" / "evidence_mesh.json"
ANNEX_VI = ROOT / "data" / "raw" / "annex_vi_clp_table_atp23_en.xlsx"

VARIANT = "headline"
DEFAULT_CASES = ("Clothianidin",)

#: Node types, in the fixed order the site assigns categorical slots to. The
#: order is the colour-blindness safety mechanism (see the dataviz palette
#: reference), so it is data, not presentation, and lives with the export.
TYPE_ORDER = ("substance", "document", "hazard", "regulatory_event")


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _ranks_by_case() -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for row in _read_csv(PROCESSED / "hewb_rank_trajectories.csv"):
        if row["variant"] == VARIANT and row["rank"]:
            out.setdefault(row["case"], {})[row["cutoff"]] = int(row["rank"])
    return out


def _action_dates() -> dict[str, str]:
    return {
        row["case"]: row["action_date"]
        for row in _read_csv(PROCESSED / "hewb_lead_times.csv")
        if row["variant"] == VARIANT and row["action_date"]
    }


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--case", action="append", default=[], help="Landmark name (repeatable)")
    p.add_argument("--max-nodes", type=int, default=800, help="Node cap per mesh")
    p.add_argument("--iterations", type=int, default=400, help="Layout iterations")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    wanted = {c.lower() for c in (args.case or DEFAULT_CASES)}
    cases = [c for c in LANDMARK_CASES if c.name.lower() in wanted]
    if not cases:
        print(f"no matching landmark; known: {', '.join(c.name for c in LANDMARK_CASES)}")
        return 2

    graph = load_graph(PROCESSED / "graph_nodes.jsonl", PROCESSED / "graph_edges.jsonl")
    # An H-code alone tells a reader nothing, so each hazard node carries the
    # CLP class it denotes, derived from Annex VI rather than transcribed.
    hazard_classes = hazard_class_by_code(load_clp(ANNEX_VI)) if ANNEX_VI.exists() else {}
    ranks, actions = _ranks_by_case(), _action_dates()
    cutoffs = list(ANNUAL_CUTOFFS)
    payload_cases = []

    for case in cases:
        if not graph.has_node(case.substance_id):
            print(f"  [skip] {case.name}: not in graph")
            continue
        mesh = build_evidence_mesh(graph, case.substance_id, cutoffs, max_nodes=args.max_nodes)
        if not mesh.nodes:
            print(f"  [skip] {case.name}: nothing knowable in range")
            continue

        index = {n.id: i for i, n in enumerate(mesh.nodes)}
        pairs = [(index[e.source], index[e.target]) for e in mesh.edges]
        positions = force_layout_3d(
            len(mesh.nodes),
            pairs,
            iterations=args.iterations,
            centre=index[mesh.center],
        )
        quality = layout_quality(positions)
        if quality.degenerate:
            # Loud rather than silent: a collapsed layout still renders and
            # still looks vaguely like a graph, which is exactly why it needs
            # to fail here instead of shipping.
            print(f"  [FAIL] {case.name}: layout degenerate, anisotropy {quality.anisotropy:.1f}")
            return 1

        case_ranks = ranks.get(case.name, {})
        payload_cases.append(
            {
                "name": case.name,
                "cas": case.cas,
                "note": case.note,
                "action_date": actions.get(case.name),
                "center": index[mesh.center],
                "truncated": mesh.truncated,
                "ranks": [case_ranks.get(c.isoformat()) for c in cutoffs],
                "types": [
                    TYPE_ORDER.index(n.type) if n.type in TYPE_ORDER else -1 for n in mesh.nodes
                ],
                "frames": [n.first_frame for n in mesh.nodes],
                "core": [1 if n.core else 0 for n in mesh.nodes],
                "labels": [n.label[:70] for n in mesh.nodes],
                "refs": [
                    n.ref
                    or (
                        "clp:" + hazard_classes[n.label.split()[0]]
                        if n.type == "hazard" and n.label.split()[0] in hazard_classes
                        else ""
                    )
                    for n in mesh.nodes
                ],
                "via": [n.via for n in mesh.nodes],
                "clp_url": CLP_REGULATION_URL,
                "xyz": [int(round(v)) for row in positions for v in row],
                "edges": [
                    v
                    for (a, b), e in zip(pairs, mesh.edges, strict=True)
                    for v in (a, b, e.first_frame)
                ],
            }
        )
        n_core = sum(1 for n in mesh.nodes if n.core)
        cross = sum(1 for e in mesh.edges if mesh.center not in (e.source, e.target))
        print(
            f"  {case.name:22s} {len(mesh.nodes):4d} nodes ({n_core} core) "
            f"{len(mesh.edges):5d} edges ({cross} cross-links) "
            f"anisotropy {quality.anisotropy:.2f}"
        )

    if not payload_cases:
        print("nothing exported")
        return 1

    payload = {
        "variant": VARIANT,
        "cutoffs": [c.isoformat() for c in cutoffs],
        "type_order": list(TYPE_ORDER),
        "cases": payload_cases,
    }
    SITE_DATA.parent.mkdir(parents=True, exist_ok=True)
    SITE_DATA.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"\nwrote {SITE_DATA.relative_to(ROOT)} ({SITE_DATA.stat().st_size / 1024:,.1f} KiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
