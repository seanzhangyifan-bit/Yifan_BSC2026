"""Stage 4 correctness check: given a synthetic junction with a KNOWN
ground-truth angle (not just known topology), does the annulus method
recover that angle and classify T / Y / ambiguous correctly?
"""

from src.crackgraph.binarize import binarize
from src.crackgraph.graph import extract_graph
from src.crackgraph.junctions import classify_junctions
from src.crackgraph.skeleton import skeletonize_and_prune
from src.crackgraph.synthetic import (
    generate_curved_t_junction,
    generate_t_junction,
    generate_y_junction,
)

# Tighter than the classification tolerance (which only needs to place a
# junction in the right bucket) -- this verifies numeric fidelity of the
# annulus estimate itself.
ANGLE_RECOVERY_TOL_DEG = 6.0

# Y-junctions merge three finite-thickness arms at one point, which rasters
# to a larger/less-symmetric blob than a T's two-arm crossing, and two of
# the three test arms are at non-axis-aligned bearings (210/330 deg) where
# skeletonization of a rotated rectangle has more discretization bias than
# the axis-aligned case. Measured directly: at this test's pixel scale
# (thickness=5, radii up to 20px) the bias is ~5-10 deg and shrinks with
# scale (confirmed by re-running at 4x size/radius, bias drops to ~2 deg)
# -- i.e. this is a real, scale-dependent discretization limit of the
# annulus method at small pixel counts, not a code bug, so the recovery
# check here uses a looser, separately-justified tolerance.
Y_ANGLE_RECOVERY_TOL_DEG = 11.0


def _run_pipeline(gray, spur_px=3, **kwargs):
    binarize_result = binarize(gray, sanity_band=(0.0, 1.0))
    skeleton_result = skeletonize_and_prune(binarize_result.mask, source_image=gray, spur_px=spur_px)
    graph_result = extract_graph(skeleton_result.skeleton)
    return classify_junctions(skeleton_result.skeleton, graph_result, **kwargs)


def test_default_window_recovers_bearing_under_jitter():
    # Locks in the ANNULUS_OUTER_PX_PLACEHOLDER=60 choice (justified by
    # scripts/window_sweep.py's measured bias/variance/RMSE sweep) as a
    # regression test: fixed-seed jittered synthetics, at the shipped
    # default annulus radii, must still recover each arm's known bearing
    # within the sweep's measured worst-case RMSE ballpark (~10 deg),
    # generously rounded up for single-sample (not aggregate) margin.
    gray = generate_t_junction(angle_deg=90.0, jitter_px=0.75, rng_seed=123)
    result = _run_pipeline(gray)  # default inner=5, outer=60
    assert result.n_deg3_total == 1
    c = result.classifications[0]
    assert c.label == "T"
    for gap in c.sector_gaps_deg:
        assert abs(gap - 90.0) < 20.0 or abs(gap - 180.0) < 20.0


def test_t_junction_90deg_recovers_known_angle():
    gray = generate_t_junction(angle_deg=90.0)
    result = _run_pipeline(gray)
    assert result.n_deg3_total == 1
    c = result.classifications[0]
    assert c.label == "T"
    right_angles = [a for a in c.sector_gaps_deg if a < 150]
    assert len(right_angles) == 2
    for a in right_angles:
        assert abs(a - 90.0) < ANGLE_RECOVERY_TOL_DEG


def test_t_junction_non_right_angle_recovers_known_angle():
    gray = generate_t_junction(angle_deg=75.0)
    result = _run_pipeline(gray)
    c = result.classifications[0]
    assert c.label == "T"
    non_host_angles = sorted(a for a in c.sector_gaps_deg if a < 150)
    assert len(non_host_angles) == 2
    assert abs(non_host_angles[0] - 75.0) < ANGLE_RECOVERY_TOL_DEG
    assert abs(non_host_angles[1] - 105.0) < ANGLE_RECOVERY_TOL_DEG


def test_y_junction_recovers_known_angles():
    gray = generate_y_junction(bearings_deg=(90.0, 210.0, 330.0))
    result = _run_pipeline(gray)
    assert result.n_deg3_total == 1
    c = result.classifications[0]
    assert c.label == "Y"
    for a in c.sector_gaps_deg:
        assert abs(a - 120.0) < Y_ANGLE_RECOVERY_TOL_DEG


def test_sector_gaps_sum_to_360_and_capture_reflex_gap():
    # Three arms clustered into a 90-deg wedge (bearings 0/45/90 deg): the
    # true sector gaps are {45, 45, 270} -- a huge reflex gap on the empty
    # side. The old unsigned-pairwise-angle method would report
    # {45, 45, 90} (sum 180, not 360) and silently lose the fact that one
    # side is a 270 deg reflex gap, not a 90 deg acute one. This is the
    # direct regression test for that fix. (Bearings closer together than
    # this, e.g. 0/30/60, make the finite-thickness arms visually overlap
    # and skeletonize into extra spurious junctions -- not a sector-gap
    # issue, just picking a clean single-junction topology to test against.)
    gray = generate_y_junction(bearings_deg=(0.0, 45.0, 90.0))
    result = _run_pipeline(gray)
    assert result.n_deg3_total == 1
    c = result.classifications[0]
    assert c.sector_gaps_deg is not None
    assert abs(sum(c.sector_gaps_deg) - 360.0) < 1e-6
    gaps_sorted = sorted(c.sector_gaps_deg)
    assert abs(gaps_sorted[0] - 45.0) < ANGLE_RECOVERY_TOL_DEG
    assert abs(gaps_sorted[1] - 45.0) < ANGLE_RECOVERY_TOL_DEG
    assert abs(gaps_sorted[2] - 270.0) < ANGLE_RECOVERY_TOL_DEG
    # Neither template fits three clustered arms -- must not be forced.
    assert c.label == "ambiguous"


def test_all_sector_gaps_sum_to_360_on_real_geometry_regression_cases():
    # Sanity net: every classified junction's gaps must sum to 360,
    # regardless of geometry (T, Y, or ambiguous) -- this is the invariant
    # the whole point of the bearings/gaps rewrite is to guarantee.
    for gray in (
        generate_t_junction(angle_deg=90.0),
        generate_t_junction(angle_deg=75.0),
        generate_y_junction(bearings_deg=(90.0, 210.0, 330.0)),
        generate_y_junction(bearings_deg=(0.0, 60.0, 180.0)),
        generate_curved_t_junction(),
    ):
        result = _run_pipeline(gray)
        for c in result.classifications:
            if c.sector_gaps_deg is not None:
                assert abs(sum(c.sector_gaps_deg) - 360.0) < 1e-6


def test_ambiguous_junction_is_not_forced_into_t_or_y():
    # bearings 0/60/180 deg -> pairwise angles (60, 120, 180): the 180 pair
    # reads as a candidate host, but the third arm sits at 60/120 to it, not
    # 90/90 -- fails the T template too. Must be surfaced as "ambiguous",
    # not silently coerced into either bucket.
    gray = generate_y_junction(bearings_deg=(0.0, 60.0, 180.0))
    result = _run_pipeline(gray)
    assert result.n_deg3_total == 1
    c = result.classifications[0]
    assert c.label == "ambiguous"
    assert result.n_ambiguous == 1


def test_curved_host_t_junction_classified_T():
    # The headline regression test for the tangent-fit estimator: the host
    # is a circular arc (radius=30) whose chord over a [5, 20] px annulus
    # reads ~152 deg -- the old chord-centroid method provably misfiled
    # this as "ambiguous". The tangents at the vertex are genuinely 180 deg
    # apart, so the fit must recover that and classify a T.
    #
    # outer_radius_px is pinned to 20 here (not the default 60) because the
    # angle-recovery assertion isolates the *bias-removal* claim: a
    # quadratic-in-arc-length only models this tightly-curved (R=30), short
    # (39 px) arc faithfully over a short window. Behavior at the default
    # window is asserted separately below (classification level only).
    gray = generate_curved_t_junction()
    result = _run_pipeline(gray, inner_radius_px=5.0, outer_radius_px=20.0)
    assert result.n_deg3_total == 1
    c = result.classifications[0]
    assert c.label == "T"
    a_max = max(c.sector_gaps_deg)
    assert abs(a_max - 180.0) < ANGLE_RECOVERY_TOL_DEG
    for a in sorted(c.sector_gaps_deg)[:2]:
        assert abs(a - 90.0) < ANGLE_RECOVERY_TOL_DEG

    # At default parameters the quadratic misfits this extreme arc somewhat
    # (host pair reads ~166 deg, not ~179), but the junction must still
    # land in the T bucket.
    result_default = _run_pipeline(gray)
    assert result_default.classifications[0].label == "T"


def test_curved_host_curvature_recovered():
    # Curvature magnitude within a factor 2 of ground truth (1/radius) --
    # loose on purpose, rasterized curvature at this pixel scale is noisy.
    # Signs must be opposite: the two host arms are the same circle
    # traversed in opposite directions away from the shared vertex.
    # Window pinned to [5, 20] for the same model-fidelity reason as above.
    radius = 30.0
    gray = generate_curved_t_junction(radius=radius)
    result = _run_pipeline(gray, inner_radius_px=5.0, outer_radius_px=20.0)
    c = result.classifications[0]
    assert c.label == "T"
    by_path = {ed.path_index: ed for ed in c.edge_directions}
    host_curvs = [by_path[p].curvature_per_px for p in c.host_path_indices]
    for kappa in host_curvs:
        assert kappa is not None
        assert 1.0 / (2 * radius) < abs(kappa) < 2.0 / radius
    assert host_curvs[0] * host_curvs[1] < 0


def test_medial_radius_widens_effective_inner_radius_at_thick_junction():
    # A thick T (thickness=15, so junction blob half-width ~7-8 px) with
    # inner_radius_px=5: without medial_radius, the fit band starts at 5px
    # from the vertex -- still inside the merged-stroke blob. With
    # medial_radius supplied, effective_inner_radius_px must widen past
    # inner_radius_px to clear the blob.
    gray = generate_t_junction(angle_deg=90.0, thickness=15, arm_length=60.0)
    binarize_result = binarize(gray, sanity_band=(0.0, 1.0))
    skeleton_result = skeletonize_and_prune(binarize_result.mask, source_image=gray, spur_px=3)
    graph_result = extract_graph(skeleton_result.skeleton)

    result_plain = classify_junctions(skeleton_result.skeleton, graph_result, inner_radius_px=5.0)
    result_medial = classify_junctions(
        skeleton_result.skeleton, graph_result, inner_radius_px=5.0,
        medial_radius=skeleton_result.medial_radius,
    )

    c_medial = result_medial.classifications[0]
    assert c_medial.vertex_halfwidth_px is not None
    assert c_medial.vertex_halfwidth_px > 5.0  # thick junction: blob wider than the plain inner radius
    for ed in c_medial.edge_directions:
        assert ed.effective_inner_radius_px >= c_medial.vertex_halfwidth_px

    c_plain = result_plain.classifications[0]
    assert c_plain.vertex_halfwidth_px is None
    for ed in c_plain.edge_directions:
        assert ed.effective_inner_radius_px == 5.0

    # Both should still agree on the classification itself (T) -- widening
    # the inner radius shouldn't change the qualitative answer here.
    assert c_medial.label == "T"
    assert c_plain.label == "T"


def test_short_abutter_flagged_insufficient_not_crashed():
    # spur_px=0.5 (well below arm_length) isolates the annulus code's own
    # "too short" detection from stage 2's separate spur-pruning, which
    # would otherwise just delete a short abutter before it ever reaches
    # stage 4.
    gray = generate_t_junction(angle_deg=90.0, arm_length=4.0)
    result = _run_pipeline(gray, spur_px=0.5, inner_radius_px=5.0, outer_radius_px=20.0)
    assert result.n_deg3_total == 1
    c = result.classifications[0]
    assert c.label == "insufficient_data"
    assert c.failure_reason == "edge_shorter_than_inner_radius"
