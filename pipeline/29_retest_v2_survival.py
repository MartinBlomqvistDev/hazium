"""Re-test V2 node embeddings on the survival panel.

The V2 gate was closed on a coverage argument: only 29.2% of the population had
walkable graph structure, so the embedding was a constant zero vector for most
substances and could not help. That number was measured over the full
population, which is 96% substances that were never EU-approved and therefore
have almost no graph presence and could never be withdrawn anyway.

On the survival panel the same measurement reads very differently: 89.4% of rows
and 94.9% of substances have walkable structure, and 98 of the 102 events sit on
walkable rows. The premise the gate rested on does not hold here, so the gate is
owed a fair re-run rather than an assumption.

Embeddings are refit once per year against that year's ``as_of`` view, never
once over the whole graph. Fitting globally would let a 2023 edge shape a 2011
row, which is exactly the leak the project's temporal discipline exists to
prevent, and it would make any improvement meaningless.

The comparison that matters is the last two rows: whether embeddings add
anything *on top of* the tabular evidence, not whether they beat approval age.

Usage:
    python pipeline/29_retest_v2_survival.py
    python pipeline/29_retest_v2_survival.py --dim 64 --seeds 3
"""

from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold

from hazium.benchmark.survival import (
    EVENT,
    SUBJECT,
    YEAR,
    PanelSpec,
    build_panel,
    feature_columns,
)
from hazium.graph.build import load_graph
from hazium.ml.baseline import make_model
from hazium.ml.embed import embedding_dataframe, fit_metapath2vec
from hazium.models import LiteratureVolumeRecord, RegulatoryEvent, SalesRecord, Substance
from hazium.resolve.names import SubstanceResolver, resolve_sales_records

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"
N_SPLITS = 5


def _load(path: Path, model):
    with path.open(encoding="utf-8") as f:
        return [model.model_validate_json(line) for line in f]


def embed_panel(graph, panel: pd.DataFrame, dim: int, seed: int) -> pd.DataFrame:
    """Embedding columns for every panel row, refit per year on that year's view.

    Args:
        graph: The full temporal graph.
        panel: The survival panel.
        dim: Embedding width.
        seed: Passed through to the walk RNG and the model.

    Returns:
        A frame indexed like ``panel`` with ``emb_0..emb_{dim-1}``.
    """
    blocks: list[pd.DataFrame] = []
    for year in sorted(panel[YEAR].unique()):
        rows = panel[panel[YEAR] == year]
        ids = rows[SUBJECT].tolist()
        view = graph.as_of(date(year, 1, 1))
        vectors = fit_metapath2vec(view, ids, dim=dim, seed=seed)
        block = embedding_dataframe(vectors, ids, dim)
        block.index = rows.index
        blocks.append(block)
        covered = sum(1 for sid in ids if sid in vectors)
        print(f"    {year}: {len(ids):>4} rows, {covered:>4} embedded ({covered / len(ids):.0%})")
    return pd.concat(blocks).loc[panel.index]


def arm(frame: pd.DataFrame, panel: pd.DataFrame, columns: list[str], seeds: range):
    y = panel[EVENT]
    aps, aucs = [], []
    for seed in seeds:
        out = np.zeros(len(y))
        splitter = StratifiedGroupKFold(n_splits=N_SPLITS, shuffle=True, random_state=seed)
        for tr, te in splitter.split(frame[columns], y, panel[SUBJECT]):
            model = make_model(y.iloc[tr], seed)
            model.fit(frame[columns].iloc[tr], y.iloc[tr])
            out[te] = model.predict_proba(frame[columns].iloc[te])[:, 1]
        aps.append(average_precision_score(y, out))
        aucs.append(roc_auc_score(y, out))
    return float(np.mean(aps)), float(np.std(aps)), float(np.mean(aucs))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dim", type=int, default=32)
    parser.add_argument("--seeds", type=int, default=3)
    args = parser.parse_args()
    seeds = range(42, 42 + args.seeds)

    graph = load_graph(PROCESSED / "graph_nodes.jsonl", PROCESSED / "graph_edges.jsonl")
    sales = resolve_sales_records(
        _load(PROCESSED / "kemi_sales.jsonl", SalesRecord),
        SubstanceResolver(_load(PROCESSED / "kemi_register_substances.jsonl", Substance)),
    )
    events = _load(PROCESSED / "eu_ppdb_events.jsonl", RegulatoryEvent)
    lit = _load(PROCESSED / "literature_volume.jsonl", LiteratureVolumeRecord)

    panel = build_panel(graph, sales, events, lit, PanelSpec())
    base = panel[EVENT].mean()
    print(f"panel: {len(panel):,} rows, {int(panel[EVENT].sum())} events, base {base:.2%}")
    print(f"\nfitting metapath2vec per year, dim={args.dim} (never once over the whole graph)")
    emb = embed_panel(graph, panel, args.dim, 42)

    frame = pd.concat([panel, emb], axis=1)
    emb_cols = list(emb.columns)
    nonzero = (emb.to_numpy() != 0).any(axis=1).mean()
    print(f"\n  rows with a non-zero embedding: {nonzero:.1%}")

    arms = {
        "age only": feature_columns(age=True, evidence=False),
        "embeddings only": emb_cols,
        "age + embeddings": feature_columns(age=True, evidence=False) + emb_cols,
        "age + evidence": feature_columns(),
        "age + evidence + embeddings": feature_columns() + emb_cols,
    }
    print("\ngrouped by substance, out-of-fold")
    results = {}
    for name, cols in arms.items():
        ap, sd, auc = arm(frame, panel, cols, seeds)
        results[name] = (ap, sd, auc)
        print(f"  {name:<30} AP {ap:.4f} (+/-{sd:.4f})  lift {ap / base:>5.2f}x  AUC {auc:.3f}")

    tabular = results["age + evidence"]
    with_emb = results["age + evidence + embeddings"]
    delta = with_emb[0] - tabular[0]
    tolerance = 2 * max(tabular[1], with_emb[1])
    print(f"\n  delta over the tabular model {delta:+.4f}, tolerance +/-{tolerance:.4f}")
    if delta > tolerance:
        print("  VERDICT: embeddings add signal. The V2 gate should open on this framing.")
    else:
        print("  VERDICT: embeddings add nothing beyond noise. The V2 gate stays closed,")
        print("  now for a reason that survives the coverage objection.")

    out = PROCESSED / "v2_survival_retest.csv"
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["arm", "average_precision", "seed_sd", "auc", "lift"])
        for name, (ap, sd, auc) in results.items():
            writer.writerow([name, f"{ap:.6f}", f"{sd:.6f}", f"{auc:.6f}", f"{ap / base:.4f}"])
    print(f"\nwrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
