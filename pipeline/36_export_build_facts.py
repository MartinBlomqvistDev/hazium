"""Export the "what was built" figures the landing page states.

Three numbers on that page were typed into JSX and all three drifted: the graph
grew, a source was added, and the test count moved twice. A site that quotes a
figure should read it from the thing that produces the figure, so this measures
them instead.

The test count is collected by running pytest's collector, which is the only
honest way to say how many tests exist. It is slow enough to be a separate step
and cheap enough to run before any deploy.

Usage:
    python pipeline/36_export_build_facts.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"
SITE_DATA = ROOT / "web" / "data" / "build.json"

#: Sources whose facts enter the graph the model reads. SGU's groundwater survey
#: is cited in the origin story and is deliberately absent: it confirms a hazard
#: after the fact and is not a model input. PubChem is absent for a different
#: reason: it feeds the structural screen, which is not a model at all.
MODEL_SOURCES = (
    "EU Pesticides DB",
    "ECHA (CLP and CLH)",
    "EFSA OpenFoodTox",
    "KemI",
    "Europe PMC",
)

#: Domains examined against the method's preconditions and rejected on the
#: evidence. Each failed differently; `README.md` records how.
GATED_DOMAINS = ("PFAS", "biocides", "food additives", "feed additives")


def _count_lines(path: Path) -> int:
    with path.open(encoding="utf-8") as f:
        return sum(1 for _ in f)


def _collect_test_count() -> int:
    """Ask pytest how many tests exist, rather than remembering."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--collect-only"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    match = re.search(r"(\d+) tests? collected", result.stdout)
    if not match:
        raise SystemExit(f"could not read a test count from pytest:\n{result.stdout[-800:]}")
    return int(match.group(1))


def main() -> int:
    nodes = _count_lines(PROCESSED / "graph_nodes.jsonl")
    edges = _count_lines(PROCESSED / "graph_edges.jsonl")
    tests = _collect_test_count()

    payload = {
        "generated": date.today().isoformat(),
        "graph_nodes": nodes,
        "graph_edges": edges,
        "model_sources": list(MODEL_SOURCES),
        "tests": tests,
        "gated_domains": list(GATED_DOMAINS),
    }
    SITE_DATA.parent.mkdir(parents=True, exist_ok=True)
    SITE_DATA.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")

    print(f"graph          {nodes:,} nodes, {edges:,} edges")
    print(f"model sources  {len(MODEL_SOURCES)}")
    print(f"tests          {tests}")
    print(f"gated domains  {len(GATED_DOMAINS)}")
    print(f"\nwrote {SITE_DATA.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
