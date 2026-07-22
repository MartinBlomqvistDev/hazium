"""Tests for the deterministic 3D layout.

Coordinates themselves are not asserted on: a force layout's exact output is an
implementation detail and pinning it would make every tuning change a test
failure. What is asserted is the behaviour that matters, namely that the layout
is reproducible, that it genuinely occupies three dimensions, and that the
diagnostic which catches collapse actually catches it.
"""

from __future__ import annotations

import numpy as np
import pytest

from hazium.graph.layout3d import force_layout_3d, layout_quality


def _ring(n: int) -> list[tuple[int, int]]:
    return [(i, (i + 1) % n) for i in range(n)]


def _hub(n: int) -> list[tuple[int, int]]:
    return [(0, i) for i in range(1, n)]


def test_layout_is_deterministic_for_a_given_seed():
    a = force_layout_3d(40, _ring(40), seed=3, iterations=60)
    b = force_layout_3d(40, _ring(40), seed=3, iterations=60)
    assert np.array_equal(a, b)


def test_different_seeds_give_different_layouts():
    a = force_layout_3d(40, _ring(40), seed=1, iterations=60)
    b = force_layout_3d(40, _ring(40), seed=2, iterations=60)
    assert not np.allclose(a, b)


def test_layout_shape_and_bounds():
    pos = force_layout_3d(50, _ring(50), iterations=60)
    assert pos.shape == (50, 3)
    # Normalised into the cube, with a little slack for floating point.
    assert np.abs(pos).max() <= 150.0 + 1e-6


def test_centre_node_sits_at_the_origin():
    pos = force_layout_3d(30, _hub(30), iterations=60, centre=0)
    assert np.allclose(pos[0], [0.0, 0.0, 0.0])


def test_a_real_shaped_mesh_is_not_degenerate():
    # A hub with cross-links, which is the shape of an evidence mesh: one focal
    # node, a few shared attributes, many peripheral nodes hanging off them.
    edges = _hub(60) + [(i, i + 1) for i in range(1, 59)]
    pos = force_layout_3d(60, edges, iterations=300)
    q = layout_quality(pos)
    assert not q.degenerate, f"layout collapsed: {q}"


def test_layout_quality_flags_a_diagonal_collapse():
    # Regression guard for a bug in this very diagnostic. Every point on the
    # x=y=z diagonal still renders and still looks like a graph, and it has
    # IDENTICAL per-axis standard deviation, so a per-axis metric scores it as
    # perfectly isotropic. Only the singular values reveal that it is a line.
    line = np.stack([np.linspace(-1, 1, 50)] * 3, axis=1)
    q = layout_quality(line)
    assert q.axis_std[0] == pytest.approx(q.axis_std[2]), "the trap: axes look equal"
    assert q.degenerate
    assert q.anisotropy > 4.0


def test_layout_quality_flags_a_planar_collapse():
    # Two dimensions of three: also degenerate, also invisible to per-axis std
    # if the plane is diagonal.
    rng = np.random.default_rng(1)
    a, b = rng.normal(0, 1, (100, 1)), rng.normal(0, 1, (100, 1))
    plane = np.hstack([a, b, a + b])  # third coordinate fully determined
    assert layout_quality(plane).degenerate


def test_layout_quality_accepts_an_isotropic_cloud():
    rng = np.random.default_rng(0)
    q = layout_quality(rng.normal(0, 1, (200, 3)))
    assert not q.degenerate


def test_layout_quality_handles_a_flattened_axis():
    rng = np.random.default_rng(0)
    flat = rng.normal(0, 1, (100, 3))
    flat[:, 2] *= 1e-12
    assert layout_quality(flat).degenerate


def test_single_node_layout():
    assert np.array_equal(force_layout_3d(1, []), np.zeros((1, 3)))


def test_graph_with_no_edges_still_lays_out():
    pos = force_layout_3d(20, [], iterations=40)
    assert pos.shape == (20, 3)
    assert np.isfinite(pos).all()


def test_rejects_non_positive_node_count():
    with pytest.raises(ValueError, match="must be positive"):
        force_layout_3d(0, [])


def test_rejects_out_of_range_edge():
    with pytest.raises(ValueError, match="out of range"):
        force_layout_3d(5, [(0, 9)])


def test_layout_stays_finite_on_a_dense_graph():
    # Dense graphs are where an uncapped step size diverges to inf/nan.
    edges = [(i, j) for i in range(25) for j in range(i + 1, 25)]
    pos = force_layout_3d(25, edges, iterations=200)
    assert np.isfinite(pos).all()
