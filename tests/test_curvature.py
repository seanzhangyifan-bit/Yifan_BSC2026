"""Curvature/tortuosity correctness checks against synthetics with known
geometry: a circular-arc host has exact closed-form tortuosity and
curvature (1/radius); straight lines must read near-zero curvature and
near-1 tortuosity; a sharp kink must show max curvature well above the
mean (the reason both numbers are reported, not just one).
"""

import math

import numpy as np
import pandas as pd

from src.crackgraph.binarize import binarize
from src.crackgraph.curvature import compute_edge_curvature
from src.crackgraph.graph import extract_graph
from src.crackgraph.skeleton import skeletonize_and_prune
from src.crackgraph.synthetic import (
    generate_curved_t_junction,
    generate_kinked_line,
    generate_t_junction,
)

# Straight geometry: measured tortuosity/curvature are not exactly 1.0/0.0
# even with zero drawn curvature, because skeleton branch points round off
# over ~thickness px right at the vertex (see generate_t_junction's own
# skeleton, measured directly: tortuosity <= 1.01, mean|kappa| <= 0.001).
STRAIGHT_TORTUOSITY_MAX = 1.02
STRAIGHT_MEAN_CURVATURE_MAX_PX_INV = 0.002

# Circular-arc recovery: measured directly at radius=30/60/100 (arc_half_angle
# =60deg), mean|kappa|/(1/radius) ranged 0.89-1.05 -- within ~12% of exact,
# the residual being pixel/skeletonization discretization noise, not a
# formula bias (see curvature.py's module docstring: the chord-midpoint-
# tangent identity is exact for circles at any window size).
CURVATURE_RECOVERY_REL_TOL = 0.25
# Tortuosity closed form for a circular arc of half-angle phi (radians):
# arc/chord = phi / (2*sin(phi/2)). Measured deviation from this at the
# default radius=30, arc_half_angle_deg=75 case was ~3%, attributed to the
# host arm's graph edge endpoint not landing exactly on the idealized
# vertex/tip due to line thickness and spur pruning.
TORTUOSITY_RECOVERY_REL_TOL = 0.10


def _run_curvature(gray, **kwargs):
    binarize_result = binarize(gray, sanity_band=(0.0, 1.0))
    skeleton_result = skeletonize_and_prune(binarize_result.mask, source_image=gray, spur_px=3)
    graph_result = extract_graph(skeleton_result.skeleton)
    return compute_edge_curvature(skeleton_result.skeleton, graph_result, **kwargs)


def _arc_tortuosity_true(arc_half_angle_deg: float) -> float:
    phi = math.radians(arc_half_angle_deg)
    return phi / (2.0 * math.sin(phi / 2.0))


def test_straight_t_junction_arms_are_near_straight():
    gray = generate_t_junction()
    result = _run_curvature(gray)
    assert result.n_edges_scanned == 3
    for edge in result.edges:
        assert edge.ok
        assert edge.tortuosity is not None
        assert edge.tortuosity < STRAIGHT_TORTUOSITY_MAX
        if edge.mean_abs_curvature_px_inv is not None:
            assert edge.mean_abs_curvature_px_inv < STRAIGHT_MEAN_CURVATURE_MAX_PX_INV


def test_curved_arc_recovers_known_curvature_and_tortuosity():
    radius = 30.0
    arc_half_angle_deg = 75.0
    gray = generate_curved_t_junction(radius=radius, arc_half_angle_deg=arc_half_angle_deg)
    result = _run_curvature(gray)

    # The two host arms are the edges with a real chord/arc gap; the
    # straight abutter reads ~1.0. Identify by tortuosity rather than a
    # hardcoded path_index, since skan's path ordering is not a documented
    # contract.
    curved_edges = [e for e in result.edges if e.tortuosity is not None and e.tortuosity > 1.02]
    assert len(curved_edges) == 2

    true_kappa = 1.0 / radius
    true_tortuosity = _arc_tortuosity_true(arc_half_angle_deg)
    for edge in curved_edges:
        assert edge.mean_abs_curvature_px_inv is not None
        rel_err_kappa = abs(edge.mean_abs_curvature_px_inv - true_kappa) / true_kappa
        assert rel_err_kappa < CURVATURE_RECOVERY_REL_TOL

        rel_err_tort = abs(edge.tortuosity - true_tortuosity) / true_tortuosity
        assert rel_err_tort < TORTUOSITY_RECOVERY_REL_TOL


def test_kinked_line_max_curvature_far_exceeds_mean():
    # A single sharp 60-deg kink concentrates almost all the direction
    # change at one point: max|kappa| should be well above mean|kappa|,
    # unlike a smoothly curved arc where they are close. This is the
    # concrete case for reporting both numbers instead of one (measured
    # directly: ratio ~4.8x at turn_deg=60).
    gray = generate_kinked_line(turn_deg=60.0)
    result = _run_curvature(gray)
    assert len(result.edges) == 1
    edge = result.edges[0]
    assert edge.mean_abs_curvature_px_inv is not None
    assert edge.max_abs_curvature_px_inv is not None
    assert edge.max_abs_curvature_px_inv > 3.0 * edge.mean_abs_curvature_px_inv


def test_short_edge_has_tortuosity_but_no_curvature_profile():
    # arm_length=5.0 makes the abutter edge shorter than 2*window_px (the
    # default window is 10px), so it can't support a windowed profile --
    # but tortuosity, which needs no window, should still be reported.
    gray = generate_t_junction(arm_length=5.0)
    result = _run_curvature(gray)
    short_edges = [e for e in result.edges if e.arc_length_px < 20.0]
    assert len(short_edges) == 1
    edge = short_edges[0]
    assert edge.ok
    assert edge.tortuosity is not None
    assert edge.curvature_profile_px_inv is None
    assert edge.mean_abs_curvature_px_inv is None


class _FakeSkeleton:
    """Minimal stand-in for skan.Skeleton exposing only what
    compute_edge_curvature reads, so degenerate polyline shapes that are
    awkward to produce via real image synthesis (a near-closed loop, a
    single-point path) can be constructed directly."""

    def __init__(self, coords: np.ndarray):
        self._coords = coords

    def path_coordinates(self, _path_index: int) -> np.ndarray:
        return self._coords


class _FakeGraphResult:
    def __init__(self, n_paths: int):
        self.summary = pd.DataFrame(index=range(n_paths))


def test_near_zero_chord_edge_reports_none_tortuosity_not_inf():
    # Loop back to (almost) the start: chord_length_px is tiny relative to
    # arc_length_px, so tortuosity would blow up or be numerically unstable
    # rather than meaningful -- must be None with a stated reason, not NaN
    # or a huge number.
    coords = np.array(
        [[0.0, 0.0], [1.0, 1.0], [2.0, 2.0], [1.0, 1.0], [0.0, 0.001]]
    )
    result = compute_edge_curvature(_FakeSkeleton(coords), _FakeGraphResult(1))
    edge = result.edges[0]
    assert edge.ok
    assert edge.tortuosity is None
    assert edge.failure_reason == "near_zero_chord_length"


def test_single_point_edge_is_flagged_not_a_crash():
    coords = np.array([[5.0, 5.0]])
    result = compute_edge_curvature(_FakeSkeleton(coords), _FakeGraphResult(1))
    edge = result.edges[0]
    assert not edge.ok
    assert edge.failure_reason == "degenerate_edge_fewer_than_2_points"
    assert edge.tortuosity is None
