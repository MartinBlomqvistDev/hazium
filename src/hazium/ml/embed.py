"""Metapath2vec node embeddings, fit fresh per ``as_of(T)`` view.

**Temporal discipline is the whole point of this module existing separately
from ``ml/baseline.py``'s call site.** An embedding fit on the full graph and
scored on a temporal split is the classic leakage that makes graph papers
irreproducible (see ``V2_SCOPE.md``): the walk could traverse an edge dated
after the cutoff, encoding future knowledge into a "pre-cutoff" feature. Every
function here takes a ``view`` (an already-``as_of``-filtered ``TemporalGraph``)
as its only source of graph structure, never the full graph, so the caller
cannot accidentally leak by passing the wrong thing -- there is no "fit once,
reuse across cutoffs" path available to get wrong.

**Method.** Not vanilla Node2Vec: this graph is heterogeneous (substance,
hazard, document, regulatory_event, product, country node types), and an
untyped walk collapses everything through whichever node type happens to have
the highest degree (hazard codes, here) -- exactly the redundant-with-existing-
columns failure mode ``V2_SCOPE.md`` measured before proposing a method. The
walk is restricted to the two edge types with genuine substance-substance
reach: ``DEGRADES_TO`` (the recovered metabolite bridge, walked as
substance <-> substance directly) and ``CLASSIFIED_AS`` (walked
substance -> hazard -> substance, i.e. shared-hazard community). ``EVIDENCED_BY``
and ``SUBJECT_OF`` are excluded: their target nodes (document,
regulatory_event) are effectively 1:1 with a single substance in this graph
(a dossier UUID and a regulatory-event node id are both minted per-substance),
so walking through them produces no cross-substance paths -- only noise.

Word2Vec's skip-gram (via ``gensim``, the one library dependency here: hand-
rolling a correct, fast negative-sampling skip-gram trainer would not be a
better use of effort than the walk generation, which *is* hand-rolled) learns
a shared embedding space over every node visited, substance and hazard alike;
only the substance rows are read out afterwards, matching how metapath2vec is
used in practice (Dong et al. 2017).

Substances with no informative-relation edges in a given ``as_of(T)`` view
(no ``DEGRADES_TO``/``CLASSIFIED_AS`` neighbour at all, even if they have
``EVIDENCED_BY`` elsewhere) never enter a walk and get an all-zero vector:
this is honest information -- "no walkable graph structure" -- not a missing
value to impute.
"""

from __future__ import annotations

import random

import numpy as np
import pandas as pd
from gensim.models import Word2Vec

from hazium.graph.store import TemporalGraph
from hazium.models import EdgeType

_WALK_EDGE_TYPES = frozenset({EdgeType.DEGRADES_TO, EdgeType.CLASSIFIED_AS})


def _walk_neighbors(view: TemporalGraph, node_id: str) -> list[str]:
    """The other endpoint of every informative edge incident to ``node_id``."""
    neighbors = []
    for edge in view.edges_of(node_id):
        if edge.predicate not in _WALK_EDGE_TYPES:
            continue
        neighbors.append(edge.object if edge.subject == node_id else edge.subject)
    return neighbors


def _random_walk(view: TemporalGraph, start: str, length: int, rng: random.Random) -> list[str]:
    """One walk from ``start``, stopping early (not restarting) if stuck.

    A shorter walk is a perfectly valid Word2Vec training sentence; forcing a
    fixed length via restarts would bias the corpus toward well-connected
    starting nodes' neighbourhoods rather than reflecting the graph honestly.
    """
    walk = [start]
    current = start
    for _ in range(length - 1):
        neighbors = _walk_neighbors(view, current)
        if not neighbors:
            break
        current = rng.choice(neighbors)
        walk.append(current)
    return walk


def generate_walks(
    view: TemporalGraph,
    substance_ids: list[str],
    walk_length: int = 40,
    num_walks: int = 5,
    seed: int = 42,
) -> list[list[str]]:
    """Metapath-guided walks, one seeded RNG stream, deterministic order.

    Sorting ``substance_ids`` before walking (rather than trusting caller
    order, which may reflect dict/set iteration) plus a single seeded
    ``random.Random`` makes this reproducible: fitting twice on the identical
    ``as_of(T)`` view yields byte-identical walks. This determinism is what
    the temporal-refit correctness test in ``tests/test_ml_embed.py`` relies
    on -- perturbing a post-cutoff edge must leave every walk unchanged.
    """
    rng = random.Random(seed)
    walks = []
    for substance_id in sorted(substance_ids):
        for _ in range(num_walks):
            walks.append(_random_walk(view, substance_id, walk_length, rng))
    return walks


def fit_metapath2vec(
    view: TemporalGraph,
    substance_ids: list[str],
    dim: int = 32,
    walk_length: int = 40,
    num_walks: int = 5,
    window: int = 5,
    epochs: int = 5,
    seed: int = 42,
) -> dict[str, np.ndarray]:
    """Fit metapath2vec on ``view`` alone; return ``{substance_id: vector}``.

    Only entries for substances that appear in at least one length->=2 walk
    are returned; ``embedding_dataframe`` fills the rest with zero vectors.
    ``workers=1`` is required, not incidental: gensim's default multi-threaded
    training is order-dependent (Hogwild-style async SGD) and not
    reproducible run-to-run even with a fixed ``seed`` -- the temporal-refit
    test would be flaky without this.
    """
    walks = generate_walks(view, substance_ids, walk_length, num_walks, seed)
    sentences = [w for w in walks if len(w) > 1]
    vectors: dict[str, np.ndarray] = {}
    if not sentences:
        return vectors
    model = Word2Vec(
        sentences=sentences,
        vector_size=dim,
        window=window,
        min_count=1,
        sg=1,
        workers=1,
        seed=seed,
        epochs=epochs,
    )
    for substance_id in substance_ids:
        if substance_id in model.wv:
            vectors[substance_id] = np.array(model.wv[substance_id], dtype=float)
    return vectors


def embedding_dataframe(
    vectors: dict[str, np.ndarray], substance_ids: list[str], dim: int
) -> pd.DataFrame:
    """One row per ``substance_ids``, columns ``emb_0..emb_{dim-1}``.

    Row order matches ``substance_ids`` exactly, so this can be
    ``pd.concat``-ed column-wise with the tabular feature matrix from
    ``ml/dataset.py`` (same index, same order, by construction).
    """
    columns = [f"emb_{i}" for i in range(dim)]
    rows = [vectors.get(sid, np.zeros(dim)) for sid in substance_ids]
    return pd.DataFrame(rows, columns=columns, index=substance_ids)
