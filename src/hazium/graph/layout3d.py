"""Deterministic 3D force-directed layout for evidence meshes.

Why this exists rather than laying out in the browser: the layout must be
identical every time the site is built, and a client-side simulation gives a
different picture on every load. Computing it here makes the coordinates data,
committed alongside the rest of the export and reviewable in a diff.

Fruchterman-Reingold with a cooling schedule. The repulsion term is O(n^2),
which is fine because these meshes are hundreds of nodes, not thousands; if that
ever changes this needs Barnes-Hut, and the node cap in the exporter is the
guard against finding out the hard way.

A degenerate layout is a real failure mode and a silent one: an unstable step
size collapses every point onto a diagonal, which still renders and still looks
vaguely like a graph. ``layout_quality`` exists to catch that, and the tests
assert on it rather than on coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

#: Iterations of the force simulation.
DEFAULT_ITERATIONS = 400

#: Initial maximum step, as a fraction of the layout scale.
INITIAL_TEMPERATURE = 0.25

#: Per-iteration cooling factor.
COOLING = 0.992

#: Half-extent of the normalised output cube.
SCALE = 150.0


@dataclass(frozen=True)
class LayoutQuality:
    """Diagnostics for a computed layout.

    Attributes:
        axis_std: Standard deviation along each axis, for information only.
        singular_values: Spread along the cloud's own principal axes.
        anisotropy: Ratio of largest to smallest singular value.
        degenerate: True when the cloud has effectively lost a dimension.
    """

    axis_std: tuple[float, float, float]
    singular_values: tuple[float, float, float]
    anisotropy: float
    degenerate: bool


def layout_quality(positions: np.ndarray, *, max_anisotropy: float = 4.0) -> LayoutQuality:
    """Measure whether a layout actually occupies three dimensions.

    Measured on singular values, not per-axis standard deviation. Per-axis
    spread cannot see collinearity: a cloud collapsed onto the x=y=z diagonal
    has *identical* standard deviation on all three axes and so scores as
    perfectly isotropic, while being exactly the one-dimensional collapse this
    check exists to catch. Singular values describe the cloud's own principal
    axes and do detect it.

    Args:
        positions: ``(n, 3)`` coordinates.
        max_anisotropy: Above this ratio the layout is treated as collapsed.

    Returns:
        Diagnostics, including a ``degenerate`` flag.
    """
    centred = positions - positions.mean(axis=0)
    sv = np.linalg.svd(centred, compute_uv=False)
    sv = np.pad(sv, (0, max(0, 3 - len(sv))))[:3]
    lo, hi = float(sv.min()), float(sv.max())
    ratio = float("inf") if lo <= hi * 1e-9 else hi / lo
    std = positions.std(axis=0)
    return LayoutQuality(
        axis_std=(float(std[0]), float(std[1]), float(std[2])),
        singular_values=(float(sv[0]), float(sv[1]), float(sv[2])),
        anisotropy=ratio,
        degenerate=ratio > max_anisotropy,
    )


def force_layout_3d(
    n_nodes: int,
    edges: list[tuple[int, int]],
    *,
    seed: int = 7,
    iterations: int = DEFAULT_ITERATIONS,
    centre: int | None = None,
) -> np.ndarray:
    """Lay out a graph in 3D, deterministically.

    Args:
        n_nodes: Number of nodes; ids are ``0..n_nodes-1``.
        edges: Index pairs. Direction is ignored, springs are symmetric.
        seed: Fixes the initial placement, so the same graph always produces
            the same picture.
        iterations: Simulation steps.
        centre: If given, the result is translated so this node sits at the
            origin, which is what the renderer expects of the focal substance.

    Returns:
        ``(n_nodes, 3)`` float array bounded by roughly ``+/-SCALE``.

    Raises:
        ValueError: If ``n_nodes`` is not positive, or an edge is out of range.
    """
    if n_nodes <= 0:
        raise ValueError("n_nodes must be positive")
    for a, b in edges:
        if not (0 <= a < n_nodes and 0 <= b < n_nodes):
            raise ValueError(f"edge ({a}, {b}) out of range for {n_nodes} nodes")

    rng = np.random.default_rng(seed)
    pos = rng.normal(0.0, 1.0, (n_nodes, 3))
    if n_nodes == 1:
        return np.zeros((1, 3))

    pairs = np.array(edges, dtype=int) if edges else np.empty((0, 2), dtype=int)
    ideal = (1.0 / n_nodes) ** (1 / 3) * 2.2
    temp = INITIAL_TEMPERATURE

    for _ in range(iterations):
        delta = pos[:, None, :] - pos[None, :, :]
        dist = np.sqrt((delta**2).sum(-1)) + 1e-6
        repulsion = (delta / dist[:, :, None] * (ideal * ideal / dist)[:, :, None]).sum(1)

        attraction = np.zeros_like(pos)
        if len(pairs):
            vec = pos[pairs[:, 0]] - pos[pairs[:, 1]]
            length = np.sqrt((vec**2).sum(-1, keepdims=True)) + 1e-6
            force = vec / length * (length * length / ideal)
            np.add.at(attraction, pairs[:, 0], -force)
            np.add.at(attraction, pairs[:, 1], force)

        disp = repulsion + attraction
        norm = np.sqrt((disp**2).sum(-1, keepdims=True)) + 1e-9
        # Cap each step by the temperature, which is what keeps the simulation
        # from diverging into the diagonal collapse this module warns about.
        pos += disp / norm * np.minimum(norm, temp)
        temp *= COOLING

    pos -= pos.mean(axis=0)
    extent = np.abs(pos).max()
    if extent > 0:
        pos *= SCALE / extent
    if centre is not None:
        pos -= pos[centre]
    return pos
