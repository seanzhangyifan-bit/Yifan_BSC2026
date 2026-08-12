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
"surface the gap, don't fill it" discipline (METHODOLOGY.md).
"""

import networkx as nx
import numpy as np

from src.crackgraph.binarize import binarize
from src.crackgraph.graph import extract_graph
from src.crackgraph.skeleton import skeletonize_and_prune
from src.crackgraph.synthetic import (
    converging_lines_ground_truth,
    crescent_ground_truth,
    generate_converging_lines,
    generate_crescent_scale_pattern,
    generate_hexagonal_grid,
    generate_hierarchical_network,
    generate_t_junction,
    generate_tapered_line,
    generate_y_junction,
    hex_flower_topology,
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


# -- case 5: crescent mesh -- actual skeletonization on the full tiled shape --


def test_case5_crescent_mesh_full_pipeline_measured():
    # Runs the ACTUAL skeletonize_and_prune/extract_graph on the full
    # tiled fish-scale mesh (not binarize-only on one isolated tile, as an
    # earlier version of this test did). A filled 2D tiling has no
    # combinatorial "expected" skeleton topology -- these are honest
    # observational measurements, not predictions.
    img = generate_crescent_scale_pattern()
    binarize_result, skeleton_result, graph_result = _run_stage123(img)

    # Real finding: the default 4x4 tiling is dense enough to trip
    # binarize()'s own sanity_band ceiling.
    assert not binarize_result.sanity_ok
    assert binarize_result.foreground_fraction > binarize_result.sanity_band[1]

    # The tiles genuinely touch (by design) -- expect one connected
    # skeleton component across the whole mesh, not 16 separate ones.
    assert _n_components(graph_result) == 1

    # Area should sit at or below the naive non-touching upper bound
    # (tiles share some boundary pixels exactly where they touch).
    radius, offset = 70.0, 30.0
    n_rows, n_cols = 4, 4
    gt_one = crescent_ground_truth(radius, offset)
    upper_bound_area = n_rows * n_cols * gt_one["area_px2"]
    assert binarize_result.mask.sum() <= upper_bound_area


# -- case 6: hexagonal network -- reproduces the known junction-splitting artifact --


def test_case6_hexagonal_network_reproduces_known_junction_splitting():
    # Replaces the earlier density-field case. At this project's own
    # already-documented thin (5px) rendering thickness, 2 of the 12 true
    # vertices of a 7-hexagon flower render as a locally wider blob that
    # splits under skeletonization -- reproduced here exactly as
    # previously characterized (see generate_hexagonal_grid's own
    # docstring), not a new/different finding.
    radius, thickness = 40.0, 5
    img = generate_hexagonal_grid(radius=radius, thickness=thickness)
    binarize_result, _, graph_result = _run_stage123(img)
    assert binarize_result.sanity_ok

    ideal = hex_flower_topology(radius=radius)
    assert ideal["n_junctions_deg3"] == 12
    assert ideal["n_edges"] == 18

    assert graph_result.n_junctions_deg_ge4 == 0
    assert graph_result.n_junctions_deg3 == 14
    assert graph_result.n_edges == 21
    assert graph_result.n_endpoints == 0


# -- case 7: illumination gradient -- spurious component, not shape fragmentation --


def test_case7_illumination_gradient_adds_spurious_component_not_fragmentation():
    # `[speculated]` scenario (binarize.py states real images have no such
    # gradient) -- now on a T-junction base (matching case 2), not
    # converging lines. Measured PRECISELY, not just "n_components goes
    # up": the T-junction's own pixels are completely unaffected (exact
    # same foreground count as the clean image) -- it does NOT fragment.
    # What actually happens is the gradient pushes plain background at the
    # image's bright edge above Otsu's threshold too, producing a second,
    # spurious, UNRELATED component elsewhere in the image. "A new
    # spurious region appears" is a different, more precise claim than
    # "the shape breaks apart," and getting this right matters.
    clean = generate_t_junction(tip_taper_frac=0.15)
    degraded = apply_illumination_gradient(clean, amplitude=60.0)

    br_clean, _, gr_clean = _run_stage123(clean)
    br_degraded, _, gr_degraded = _run_stage123(degraded)

    assert _n_components(gr_clean) == 1
    assert _n_components(gr_degraded) == 2

    from scipy.ndimage import label as ndi_label

    labeled, n = ndi_label(br_degraded.mask)
    assert n == 2
    components = []
    for i in range(1, n + 1):
        ys, xs = np.where(labeled == i)
        components.append({"size": len(ys), "col_span": int(xs.max() - xs.min()) + 1})
    components.sort(key=lambda c: c["size"])

    # the larger component is the T-junction itself, pixel-for-pixel
    # identical in size to the clean mask's own foreground count -- proof
    # the real shape is untouched, not merely "mostly" intact.
    assert components[1]["size"] == int(br_clean.mask.sum())
    # the smaller component is a thin spurious strip running the full
    # image height at the bright edge, only 1px wide -- not a broken-off
    # piece of the T-junction (which is >=5px thick everywhere).
    assert components[0]["col_span"] <= 2


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
