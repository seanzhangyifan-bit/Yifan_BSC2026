"""Pipeline-integration checks for the synthetic-benchmark matrix (step 2):
each of the 9 cases run through the REAL binarize -> skeletonize_and_prune ->
extract_graph chain, at the pipeline's own PRODUCTION defaults (spur_px =
SPUR_PX_PLACEHOLDER, sanity_band = binarize()'s own default) -- unlike
test_grid_synthetic.py's `_run_stage123`, which deliberately overrides both
to isolate raw topology from real pruning/threshold behavior, this file's
whole point is to exercise that real behavior, not bypass it.

Every expected value below was measured directly (see the exploratory pass
recorded in this file's own commit message), not predicted in advance --
several cases turned up genuine, sometimes surprising findings (case 6's
diagonal-adjacency merging, case 9's exact one-sub-branch loss), which this
file locks in as regression coverage, consistent with this project's
"surface the gap, don't fill it" discipline (CLAUDE.md).
"""

import networkx as nx
import numpy as np
import pytest
from skimage.measure import perimeter as sk_perimeter

from src.crackgraph.binarize import binarize
from src.crackgraph.graph import extract_graph
from src.crackgraph.skeleton import skeletonize_and_prune
from src.crackgraph.synthetic import (
    _crescent_mask,
    converging_lines_ground_truth,
    crescent_ground_truth,
    generate_converging_lines,
    generate_crescent_scale_pattern,
    generate_density_gradient_field,
    generate_hierarchical_network,
    generate_t_junction,
    generate_tapered_line,
    generate_y_junction,
    hierarchical_network_topology,
)
from src.crackgraph.synthetic_degradation import apply_debris, apply_illumination_gradient, apply_jpeg_blocking


def _run_stage123(gray: np.ndarray):
    """Full stage 1-3 at PRODUCTION defaults -- no spur_px/sanity_band
    override, unlike test_grid_synthetic.py's own helper of the same
    name, since testing the real default behavior is this file's point.
    """
    binarize_result = binarize(gray)
    skeleton_result = skeletonize_and_prune(binarize_result.mask, source_image=gray)
    graph_result = extract_graph(skeleton_result.skeleton)
    return binarize_result, skeleton_result, graph_result


def _n_components(graph_result) -> int:
    """Connected-component count via networkx on the graph's own edge
    list -- the same construction scripts/export_crack_stats.py's
    compute_row() uses for its own n_components column."""
    G = nx.from_pandas_edgelist(
        graph_result.summary, source="node_id_src", target="node_id_dst", edge_attr="branch_distance",
    )
    return nx.number_connected_components(G)


# -- case 1: tapered line -- does a realistic threshold clip the dim tip? --


def test_case1_tapered_line_otsu_truncates_the_dim_tip():
    length = 200.0
    img = generate_tapered_line(length=length, max_thickness=16.0, min_thickness=0.0)
    binarize_result, skeleton_result, graph_result = _run_stage123(img)

    assert binarize_result.sanity_ok
    # single unbroken skeleton path -- the taper doesn't fragment.
    assert graph_result.n_edges == 1
    assert graph_result.n_endpoints == 2
    assert graph_result.n_junctions_deg3 == 0

    # The actual point of this case: Otsu's threshold (data-driven, not
    # asserted here) sits between tip_value and fg_value, so it clips some
    # of the geometric taper before the true 200px length ends. Measured
    # directly: ~162px survives at threshold=~92 (well inside
    # tip_value=60..fg_value=230) -- asserting the *direction* and a
    # comfortable margin, not the exact pixel count, so this doesn't
    # become brittle to a 1-pixel skimage/Otsu implementation drift.
    cols = np.where(binarize_result.mask.any(axis=0))[0]
    measured_span_px = int(cols.max() - cols.min())
    assert measured_span_px < 0.9 * length, (
        "expected the dim tip to be measurably truncated by a realistic threshold"
    )
    assert measured_span_px > 0.5 * length, (
        "truncation should be partial, not eat the whole shape"
    )


# -- case 2: T/Y-junction -- basic topology recovery (angle recovery stays validation_gallery.py's job) --


def test_case2_t_junction_topology_recovers_exactly():
    img = generate_t_junction(tip_taper_frac=0.15)
    _, _, graph_result = _run_stage123(img)
    assert graph_result.n_endpoints == 3
    assert graph_result.n_junctions_deg3 == 1
    assert graph_result.n_junctions_deg_ge4 == 0
    assert graph_result.n_edges == 3


def test_case2_y_junction_topology_recovers_exactly():
    img = generate_y_junction(tip_taper_frac=0.15)
    _, _, graph_result = _run_stage123(img)
    assert graph_result.n_endpoints == 3
    assert graph_result.n_junctions_deg3 == 1
    assert graph_result.n_junctions_deg_ge4 == 0
    assert graph_result.n_edges == 3


# -- case 3: converging lines -- does the merge point become a real junction? --


def test_case3_converging_lines_merge_forms_a_real_t_junction():
    # Resolves the "open question" the plan flagged: measured directly,
    # the merged wedge's skeleton is NOT one smooth pass-through path --
    # the two back arms meet at a genuine degree-3 junction, continuing
    # on as a single arm to the (also tapered) front tip. 3 endpoints (2
    # back tips + 1 front tip), 1 junction, 3 edges, all one component.
    img = generate_converging_lines()
    binarize_result, _, graph_result = _run_stage123(img)
    assert binarize_result.sanity_ok
    assert graph_result.n_endpoints == 3
    assert graph_result.n_junctions_deg3 == 1
    assert graph_result.n_junctions_deg_ge4 == 0
    assert graph_result.n_edges == 3
    assert _n_components(graph_result) == 1


# -- case 4: hierarchical brick network -- does SPUR_PX_PLACEHOLDER behave as claimed? --


def test_case4_hierarchical_network_25px_subbranches_survive_pruning():
    img = generate_hierarchical_network(sub_branch_length=25.0)
    binarize_result, _, graph_result = _run_stage123(img)
    assert binarize_result.sanity_ok
    expected = hierarchical_network_topology(n_courses=3, n_bricks_per_course=3, sub_branches_per_primary=3)
    assert graph_result.n_junctions_deg_ge4 == expected["n_junctions_deg_ge4"] == 0
    assert graph_result.n_junctions_deg3 == expected["n_junctions_deg3"]
    assert graph_result.n_endpoints == expected["n_endpoints"]
    assert graph_result.n_edges == expected["n_edges"]


def test_case4_hierarchical_network_12px_subbranches_are_pruned_away():
    # The actual point of this case: sub_branch_length=12 is BELOW
    # SPUR_PX_PLACEHOLDER=15, so measured topology should match the
    # PRIMARY-LAYER-ONLY formula (sub_branches_per_primary=0), not the
    # pre-pruning-with-subs one -- i.e. every sub-branch stub should be
    # gone, not just shortened. Measured directly: exact match.
    img = generate_hierarchical_network(sub_branch_length=12.0)
    binarize_result, _, graph_result = _run_stage123(img)
    assert binarize_result.sanity_ok
    expected_primary_only = hierarchical_network_topology(
        n_courses=3, n_bricks_per_course=3, sub_branches_per_primary=0
    )
    assert graph_result.n_junctions_deg_ge4 == expected_primary_only["n_junctions_deg_ge4"] == 0
    assert graph_result.n_junctions_deg3 == expected_primary_only["n_junctions_deg3"]
    assert graph_result.n_endpoints == expected_primary_only["n_endpoints"]
    assert graph_result.n_edges == expected_primary_only["n_edges"]


# -- case 5: crescent tiles -- binarize only, no crack network to skeletonize --


def test_case5_crescent_binarize_area_and_perimeter_close_to_closed_form():
    radius, offset = 70.0, 30.0
    size = 300
    gray = np.full((size, size), 10.0)
    mask_true = _crescent_mask((size, size), (150.0, 130.0), radius, offset)
    gray[mask_true] = 230.0
    gt = crescent_ground_truth(radius, offset)

    binarize_result = binarize(gray)
    assert binarize_result.sanity_ok
    measured_area = int(binarize_result.mask.sum())
    assert measured_area == pytest.approx(gt["area_px2"], rel=0.02)

    # skimage's pixel-boundary perimeter is a well-known slight
    # OVERestimate of a continuous boundary's true length (a staircase
    # walks further than the smooth curve it approximates) -- `[interpreted]`,
    # not exact, measured directly at ~+2% here, so the tolerance below is
    # one-directional and documented, not a blind wide band.
    measured_perimeter = sk_perimeter(binarize_result.mask)
    assert gt["perimeter_px"] <= measured_perimeter <= gt["perimeter_px"] * 1.05


# -- case 6: density field -- does "never overlap" mean "always independent"? --


def test_case6_density_field_diagonal_adjacency_merges_some_components():
    # The real, measured finding (not assumed): step 1's non-overlap
    # guarantee only forbids sharing a pixel (4-connectivity-safe), not a
    # minimum gap -- some segment pairs land diagonally adjacent (touching
    # only at a pixel corner), and skeletonization's own connectivity
    # treats that as connected. Measured directly: 85 segments, 85
    # components in the raw Otsu mask under 4-connectivity, but only 77
    # after skeletonize_and_prune -- 8 pairs fuse. This is the honest
    # result, not the naively-hoped-for "n_components == 85".
    n_segments_per_zone = (60, 20, 5)
    img = generate_density_gradient_field(n_segments_per_zone=n_segments_per_zone)
    binarize_result, _, graph_result = _run_stage123(img)
    assert binarize_result.sanity_ok

    from scipy.ndimage import label as ndi_label

    total_segments = sum(n_segments_per_zone)
    _, n_components_4conn = ndi_label(binarize_result.mask)  # scipy default = 4-connectivity
    assert n_components_4conn == total_segments, "the raw Otsu mask itself should show every segment separate"

    n_components_measured = _n_components(graph_result)
    assert n_components_measured < total_segments, (
        "expected some diagonal-adjacency merging in the real pipeline, not full independence"
    )
    _, n_components_8conn = ndi_label(binarize_result.mask, structure=np.ones((3, 3)))
    assert n_components_measured == n_components_8conn, (
        "the skeleton's merge count should match 8-connectivity component counting on the same mask"
    )


# -- case 7: illumination gradient -- does it actually fragment the shape? --


def test_case7_illumination_gradient_fragments_the_shape():
    # `[speculated]` scenario (binarize.py states real images have no such
    # gradient) -- but measured directly here, the effect IS real: Otsu's
    # single global threshold, recomputed over the gradient-shifted
    # histogram, drops part of a thin/dim region and increases
    # n_components -- a genuine, reportable consequence of the assumption
    # this case tests, not asserted a priori.
    clean = generate_converging_lines()
    degraded = apply_illumination_gradient(clean, amplitude=60.0)

    _, _, gr_clean = _run_stage123(clean)
    _, _, gr_degraded = _run_stage123(degraded)

    assert _n_components(gr_clean) == 1
    assert _n_components(gr_degraded) > _n_components(gr_clean), (
        "expected the illumination gradient to measurably fragment the shape"
    )


# -- case 8: JPEG blocking -- does it corrupt topology at this quality/scale? --


def test_case8_jpeg_blocking_does_not_change_topology_at_q15():
    # Closes the gap named in skeleton_loop_sweep.py:25. Measured directly:
    # a NULL result at this specific quality/scale -- topology is bit-for-
    # bit identical clean vs. degraded. A real, valid finding (the
    # pipeline is robust to this level of compression here), not a weaker
    # placeholder -- and still a genuine regression guard: a future
    # libjpeg/Pillow version producing different quantization here would
    # be caught by this test changing.
    clean = generate_hierarchical_network(sub_branch_length=25.0)
    degraded = apply_jpeg_blocking(clean, quality=15)

    _, _, gr_clean = _run_stage123(clean)
    _, _, gr_degraded = _run_stage123(degraded)

    assert gr_degraded.n_endpoints == gr_clean.n_endpoints
    assert gr_degraded.n_junctions_deg3 == gr_clean.n_junctions_deg3
    assert gr_degraded.n_junctions_deg_ge4 == gr_clean.n_junctions_deg_ge4 == 0
    assert gr_degraded.n_edges == gr_clean.n_edges


# -- case 9: debris -- bridged, fragmented, or something else entirely? --


def test_case9_debris_loses_exactly_one_subbranch_not_bridged_or_fragmented():
    # The falsifiable claim case 9 was built to test, and the actual
    # measured answer is more specific than a binary bridged/fragmented
    # split: at this exact seed, one dark speck lands squarely enough on
    # one sub-branch stub that the whole stub (its T-junction, both its
    # edges, and its tip endpoint) is lost after pruning -- everything
    # else (the primary brick layer, the other 8 sub-branches) survives
    # untouched. Not "bridged" (topology would match clean exactly, as
    # case 8 shows it can) and not "fragmented" (component/edge counts go
    # DOWN, not up) -- a third, distinct, honestly-reported outcome.
    clean = generate_hierarchical_network(sub_branch_length=25.0)
    degraded = apply_debris(clean, n_specks=40, speck_radius_range_px=(1.0, 4.0), rng_seed=0)

    _, _, gr_clean = _run_stage123(clean)
    _, _, gr_degraded = _run_stage123(degraded)

    assert gr_clean.n_endpoints - gr_degraded.n_endpoints == 1
    assert gr_clean.n_junctions_deg3 - gr_degraded.n_junctions_deg3 == 1
    assert gr_clean.n_edges - gr_degraded.n_edges == 2
    assert gr_degraded.n_junctions_deg_ge4 == 0
    # not a full fragmentation: still one connected primary network.
    assert _n_components(gr_degraded) == _n_components(gr_clean) == 1
