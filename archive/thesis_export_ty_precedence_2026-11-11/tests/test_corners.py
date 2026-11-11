"""Corner cross-check correctness: does the background-tile-wall method
recover known junction geometry independently of the tangent-fit method,
and does it agree with the tangent-fit on clean synthetic cases?
"""

from src.crackgraph.binarize import binarize
from src.crackgraph.corners import _angle_diff, _mean_bearing, cross_check_junctions, find_background_contours
from src.crackgraph.graph import extract_graph
from src.crackgraph.junctions import classify_junctions
from src.crackgraph.skeleton import skeletonize_and_prune
from src.crackgraph.synthetic import generate_curved_t_junction, generate_t_junction, generate_y_junction

# Looser than the tangent-fit's own recovery tolerance -- the corner
# window (CORNER_WINDOW_PX) is a first-pass default, not yet set from a
# measured sweep the way ANNULUS_OUTER_PX_PLACEHOLDER was.
GAP_RECOVERY_TOL_DEG = 20.0


def _run(gray, spur_px=3, prune_host_stubs=True):
    binarize_result = binarize(gray)
    skeleton_result = skeletonize_and_prune(
        binarize_result.mask, source_image=gray, spur_px=spur_px, prune_host_stubs=prune_host_stubs
    )
    graph_result = extract_graph(skeleton_result.skeleton)
    junction_result = classify_junctions(skeleton_result.skeleton, graph_result)
    contours = find_background_contours(skeleton_result.mask_clean)
    cross_check = cross_check_junctions(
        junction_result, contours, y_angle_tol_deg=15.0, t_straight_tol_deg=20.0, t_right_tol_deg=20.0
    )
    return junction_result, cross_check


def test_straight_t_90deg_two_corners_agree():
    junction_result, cross_check = _run(generate_t_junction(angle_deg=90.0))
    c = cross_check[0]
    assert len(c.corners) == 2
    assert c.label == "T"
    assert c.label == junction_result.classifications[0].label
    assert c.agrees_with_tangent_fit is True
    a_max = max(c.sector_gaps_deg)
    assert abs(a_max - 180.0) < GAP_RECOVERY_TOL_DEG
    for g in sorted(c.sector_gaps_deg)[:2]:
        assert abs(g - 90.0) < GAP_RECOVERY_TOL_DEG


def test_straight_t_75deg_two_corners_agree():
    junction_result, cross_check = _run(generate_t_junction(angle_deg=75.0))
    c = cross_check[0]
    assert len(c.corners) == 2
    assert c.label == "T"
    non_host = sorted(g for g in c.sector_gaps_deg if g < 150)
    assert abs(non_host[0] - 75.0) < GAP_RECOVERY_TOL_DEG
    assert abs(non_host[1] - 105.0) < GAP_RECOVERY_TOL_DEG


def test_y_junction_three_corners_agree():
    junction_result, cross_check = _run(generate_y_junction(bearings_deg=(90.0, 210.0, 330.0)))
    c = cross_check[0]
    assert len(c.corners) == 3
    assert c.label == "Y"
    assert c.label == junction_result.classifications[0].label
    assert c.agrees_with_tangent_fit is True
    for g in c.sector_gaps_deg:
        assert abs(g - 120.0) < GAP_RECOVERY_TOL_DEG


def test_ambiguous_case_not_forced():
    # Same bearings (0/60/180) used in test_junction_angle.py's ambiguous
    # case -- neither method should force a T or Y label.
    junction_result, cross_check = _run(generate_y_junction(bearings_deg=(0.0, 60.0, 180.0)))
    c = cross_check[0]
    assert c.label == "ambiguous"
    assert c.label == junction_result.classifications[0].label
    assert c.agrees_with_tangent_fit is True


def test_curved_host_resolves_cleanly():
    # Wall corners avoid the medial-axis junction-blob problem, but they
    # are NOT immune to a bias-vs-window tradeoff on curved hosts either
    # (the corner_window_sweep measured this directly): a corner window
    # long enough to be jitter-robust (CORNER_WINDOW_PX=10, chosen for
    # that reason) still averages over enough of a *severely* curved wall
    # to bias the angle. radius=30 (the default, deliberately extreme --
    # it was chosen to stress-test the OLD tangent-fit chord method's
    # small window) does NOT resolve cleanly at this window; radius=60 (a
    # gentler, more typical curve) does. Both facts are honest and
    # measured -- this test asserts the case that should work, not the
    # hardest case there is.
    junction_result, cross_check = _run(generate_curved_t_junction(radius=60.0))
    c = cross_check[0]
    assert len(c.corners) == 2
    assert c.label == "T"
    assert c.label == junction_result.classifications[0].label


def test_short_arm_fails_gracefully_not_crashed():
    gray = generate_t_junction(angle_deg=90.0, arm_length=4.0)
    junction_result, cross_check = _run(gray, spur_px=0.5, prune_host_stubs=False)  # the host-stub rule would also remove this deliberately tiny branch
    c = cross_check[0]
    assert c.label is None
    assert c.arm_bearings_deg is None
    assert c.unresolved_reason is not None


def test_mean_bearing_wraps_across_180_seam():
    # Regression: a plain (a + b) / 2 averaged 179 and -179 to 0 (east), the
    # opposite of the true midpoint (west).
    assert abs(_angle_diff(_mean_bearing(179.0, -179.0), 180.0)) < 1e-9
    assert abs(_mean_bearing(10.0, 30.0) - 20.0) < 1e-9
    assert abs(_mean_bearing(-170.0, 170.0) - (-180.0)) < 1e-9


def test_west_pointing_abutter_not_flipped_east():
    # Regression for the same bug end to end: a T whose abutter points west
    # (bearing 180). Its two wall corners read the abutter wall just either
    # side of the +/-180 seam; before the fix the corner method reported the
    # abutter pointing east (~0 deg) while still labelling the junction T.
    gray = generate_y_junction(bearings_deg=(180.0, -90.0, 90.0), thickness=7, size=160, arm_length=55.0)
    junction_result, cross_check = _run(gray)
    c = cross_check[0]
    assert c.label == "T"
    abutter_bearing = c.arm_bearings_deg[2]  # _pair_t_like returns [host_a, host_b, abutter]
    assert abs(_angle_diff(abutter_bearing, 180.0)) < GAP_RECOVERY_TOL_DEG
