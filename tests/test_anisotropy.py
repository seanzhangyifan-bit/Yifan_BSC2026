"""Anisotropy-index correctness checks: pure-math sanity checks on the
corrected axial circular-statistics formula (guarding the traceless-matrix
divide-by-zero bug the formula originally had), plus recovery checks
against synthetic oriented-segment fields with known bearing
distributions -- including the documented 2nd-order-tensor blind spot for
an equal-weight orthogonal grid, which the raw orientation histogram (not
the scalar index) is meant to catch.
"""

import numpy as np

from src.crackgraph.anisotropy import (
    anisotropy_index_from_bearings,
    compute_anisotropy,
)
from src.crackgraph.binarize import binarize
from src.crackgraph.graph import extract_graph
from src.crackgraph.skeleton import skeletonize_and_prune
from src.crackgraph.synthetic import generate_oriented_segment_field, generate_t_junction

# Aligned/random-field tolerances are finite-sample noise, not estimator
# bias: measured directly at n_segments=60-80 (~1/sqrt(n_segments) ~ 0.13),
# comfortably covered by 0.15.
ANISOTROPY_LOW_TOL = 0.15
ANISOTROPY_HIGH_MIN = 0.8
CIRCULAR_BEARING_TOL_DEG = 10.0


def _circular_diff_deg(a: float, b: float, period: float = 180.0) -> float:
    d = abs(a - b) % period
    return min(d, period - d)


def _run_anisotropy(gray, **kwargs):
    binarize_result = binarize(gray, sanity_band=(0.0, 1.0))
    skeleton_result = skeletonize_and_prune(binarize_result.mask, source_image=gray, spur_px=3)
    graph_result = extract_graph(skeleton_result.skeleton)
    return compute_anisotropy(skeleton_result.skeleton, graph_result, **kwargs)


def test_all_equal_bearings_gives_exactly_one_not_nan():
    # Regression guard for the original bug: a naive doubled-angle matrix
    # ratio is 0/0 (division by zero) exactly in this case, since that
    # matrix is always traceless. The corrected formula must give exactly
    # A=1.0, not NaN/inf.
    A, dominant = anisotropy_index_from_bearings([30.0, 30.0, 30.0, 30.0])
    assert A == 1.0
    assert _circular_diff_deg(dominant, 30.0) < 1e-9


def test_orthogonal_equal_weights_gives_exactly_zero():
    # The documented 2nd-order-tensor blind spot, in closed form: two
    # bearings 90 deg apart with equal weight fold to exactly opposite
    # points after doubling and cancel -- A=0 exactly, not a bug.
    A, _ = anisotropy_index_from_bearings([0.0, 90.0], weights=[1.0, 1.0])
    assert A < 1e-9  # exactly 0 up to floating-point sin/cos roundoff


def test_single_direction_field_has_high_anisotropy():
    gray = generate_oriented_segment_field(bearings_deg=[0.0], n_segments=60, rng_seed=1)
    result = _run_anisotropy(gray)
    assert result.anisotropy_index > ANISOTROPY_HIGH_MIN
    assert _circular_diff_deg(result.dominant_bearing_deg, 0.0) < CIRCULAR_BEARING_TOL_DEG


def test_uniform_random_field_has_low_anisotropy():
    gray = generate_oriented_segment_field(bearings_deg=None, n_segments=60, rng_seed=2)
    result = _run_anisotropy(gray)
    assert result.anisotropy_index < ANISOTROPY_LOW_TOL


def test_equal_weight_orthogonal_grid_is_blind_spot_but_histogram_reveals_it():
    gray = generate_oriented_segment_field(
        bearings_deg=[0.0, 90.0], bearing_weights=[0.5, 0.5], n_segments=80, rng_seed=3
    )
    result = _run_anisotropy(gray)

    # The scalar index reads as isotropic -- documented blind spot, not a bug.
    assert result.anisotropy_index < ANISOTROPY_LOW_TOL

    # But the histogram must clearly show two separated peaks (near 0 and
    # 90 deg), proving the information is there even though the 2nd-order
    # scalar can't see it. "Separated" = the two largest bins are not
    # adjacent (>= 5 bins apart out of 18, i.e. >= ~50 deg).
    counts = result.histogram_weighted_counts
    top_two = np.argsort(counts)[-2:]
    total = counts.sum()
    assert counts[top_two[0]] > 0.1 * total
    assert counts[top_two[1]] > 0.1 * total
    assert abs(int(top_two[0]) - int(top_two[1])) >= 5


def test_unequal_weight_orthogonal_grid_has_moderate_anisotropy():
    gray = generate_oriented_segment_field(
        bearings_deg=[0.0, 90.0], bearing_weights=[0.8, 0.2], n_segments=80, rng_seed=4
    )
    result = _run_anisotropy(gray)
    assert result.anisotropy_index > 0.3
    assert _circular_diff_deg(result.dominant_bearing_deg, 0.0) < CIRCULAR_BEARING_TOL_DEG


def test_histogram_is_consistent_with_scalar_index():
    # Internal-consistency check: the histogram is supposed to be a
    # faithful (if coarsened) summary of the same underlying weighted
    # bearing distribution the scalar index is computed from -- recomputing
    # the index from the histogram's bin centers/weights should recover
    # very nearly the same A and dominant bearing as the direct computation,
    # on a network with a real, non-trivial edge-orientation mix (a T
    # junction's two collinear host arms + one perpendicular abutter).
    gray = generate_t_junction()
    result = _run_anisotropy(gray)

    bin_centers = (result.histogram_bin_edges_deg[:-1] + result.histogram_bin_edges_deg[1:]) / 2.0
    A_from_hist, dom_from_hist = anisotropy_index_from_bearings(
        bin_centers, weights=result.histogram_weighted_counts
    )
    # 10-deg-wide bins coarsen the exact per-sample bearings, so a few
    # degrees of slop is expected from binning alone (measured directly:
    # ~5 deg here), not a sign the histogram is a bad summary.
    assert abs(A_from_hist - result.anisotropy_index) < 0.05
    assert _circular_diff_deg(dom_from_hist, result.dominant_bearing_deg) < 8.0
