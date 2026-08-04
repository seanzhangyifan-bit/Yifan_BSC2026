"""Correctness checks for the mesh/network generators (generate_grid,
generate_wavy_grid, generate_hexagonal_grid, generate_grid_with_flakes) --
crack_stats-scoped: stage 1-3 (binarize/skeletonize/graph) and flaking.py
only, no junction/curvature/anisotropy classification.

Unlike every single-junction generator, a mesh's ground truth is a network
invariant (total edge/node count, total length), and two of the four cases
below have a real, verified deviation from the naive combinatorial ideal --
see each generator's own docstring for why, and each test's assertions for
the actual, reproducible measured value rather than a forced pass.
"""

import numpy as np
from scipy.ndimage import distance_transform_edt
from skimage.draw import disk

from src.crackgraph.binarize import binarize
from src.crackgraph.flaking import exclude_flaking_regions
from src.crackgraph.graph import extract_graph
from src.crackgraph.skeleton import skeletonize_and_prune
from src.crackgraph.synthetic import (
    generate_grid,
    generate_grid_with_flakes,
    generate_hexagonal_grid,
    generate_wavy_grid,
    grid_topology,
    hex_flower_topology,
    wavy_line_arc_length_px,
)


def _run_stage123(gray: np.ndarray, spur_px: float = 3.0):
    binarize_result = binarize(gray, sanity_band=(0.0, 1.0))
    skeleton_result = skeletonize_and_prune(binarize_result.mask, source_image=gray, spur_px=spur_px)
    graph_result = extract_graph(skeleton_result.skeleton)
    return binarize_result, skeleton_result, graph_result


# -- generate_grid: exact topology across grid widths and densities ---------


def test_grid_topology_matches_formula_across_spacings():
    # "Grid width" (crack density) sweep at fixed n_lines=3 -- size is
    # scaled with spacing so every line still fits inside its margin at
    # every spacing tried (a spacing too large for a fixed image size
    # would clip lines against the crop edge, a setup bug, not a pipeline
    # finding -- confirmed by hand before picking this scaling).
    n_lines = 3
    margin = 30.0
    for spacing in (35.0, 50.0, 70.0, 100.0, 140.0):
        size = int(2 * margin + spacing * (n_lines + 1))
        gray = generate_grid(size=size, n_lines=n_lines, spacing=spacing, margin=margin, thickness=5)
        _, _, graph_result = _run_stage123(gray)
        expected = grid_topology(n_lines, n_lines)
        assert graph_result.n_endpoints == expected["n_endpoints"]
        assert graph_result.n_junctions_deg_ge4 == expected["n_junctions_deg_ge4"]
        assert graph_result.n_junctions_deg3 == 0
        assert graph_result.n_edges == expected["n_edges"]


def test_grid_topology_matches_formula_across_line_counts():
    spacing = 70.0
    margin = 30.0
    for n_lines in (2, 3, 4):
        size = int(2 * margin + spacing * (n_lines + 1))
        gray = generate_grid(size=size, n_lines=n_lines, spacing=spacing, margin=margin, thickness=5)
        _, _, graph_result = _run_stage123(gray)
        expected = grid_topology(n_lines, n_lines)
        assert graph_result.n_endpoints == expected["n_endpoints"]
        assert graph_result.n_junctions_deg_ge4 == expected["n_junctions_deg_ge4"]
        assert graph_result.n_edges == expected["n_edges"]


def test_grid_total_length_scales_linearly_with_spacing():
    # Each of the 2*n_lines lines spans the same (size - 2*margin) run
    # regardless of spacing when size is scaled to keep margin fixed --
    # total skeleton length should scale with that run length, i.e.
    # linearly with spacing at fixed n_lines.
    n_lines = 3
    margin = 30.0
    lengths = []
    spacings = (35.0, 70.0, 140.0)
    for spacing in spacings:
        size = int(2 * margin + spacing * (n_lines + 1))
        gray = generate_grid(size=size, n_lines=n_lines, spacing=spacing, margin=margin, thickness=5)
        _, _, graph_result = _run_stage123(gray)
        lengths.append(float(graph_result.summary["branch_distance"].sum()))
    # doubling then quadrupling spacing should roughly double/quadruple length
    assert 1.8 < lengths[1] / lengths[0] < 2.2
    assert 3.6 < lengths[2] / lengths[0] < 4.4


# -- generate_wavy_grid: length recovery holds, topology genuinely doesn't --


def test_wavy_grid_length_matches_closed_form_arc_length():
    n_lines, spacing, margin, thickness = 3, 70.0, 30.0, 5
    amplitude, wavelength = 10.0, 110.0
    size = 340
    gray = generate_wavy_grid(
        size=size, n_lines=n_lines, spacing=spacing, margin=margin, thickness=thickness,
        amplitude=amplitude, wavelength=wavelength,
    )
    _, _, graph_result = _run_stage123(gray)
    measured_total_len = float(graph_result.summary["branch_distance"].sum())

    run_px = size - 2 * margin
    horiz_arc = wavy_line_arc_length_px(run_px, amplitude=amplitude, wavelength=wavelength)
    expected_total_len = n_lines * horiz_arc + n_lines * run_px
    assert abs(measured_total_len - expected_total_len) / expected_total_len < 0.05


def test_wavy_grid_crossings_split_into_pairs_of_degree3_not_clean_degree4():
    # The interesting empirical result, not a bug: a degree>=4 skeleton
    # crossing is a non-generic, unstable configuration, so any local tilt
    # at a crossing resolves it into a *pair* of degree-3 points instead --
    # verified stable at this amplitude/wavelength (6 of the 9 crossings
    # split, 3 remain clean, giving 12 endpoints / 12 deg3 / 3 deg4+ / 30
    # edges instead of the straight grid's clean 12/0/9/24).
    gray = generate_wavy_grid(
        size=340, n_lines=3, spacing=70.0, margin=30.0, thickness=5,
        amplitude=10.0, wavelength=110.0,
    )
    _, _, graph_result = _run_stage123(gray)
    straight_expected = grid_topology(3, 3)

    assert graph_result.n_endpoints == straight_expected["n_endpoints"]
    # every split crossing adds one junction node vs the straight case
    assert graph_result.n_junctions_deg3 + graph_result.n_junctions_deg_ge4 > 9
    assert graph_result.n_edges > straight_expected["n_edges"]


# -- generate_hexagonal_grid: ideal ground truth vs the real, verified gap --


def test_hexagonal_grid_ideal_topology_is_all_degree3_no_endpoints():
    # The idealized combinatorial ground truth itself (no rasterization
    # involved) -- a sanity check on hex_flower_topology's own reduction
    # logic, independent of whether real skeletonization matches it.
    expected = hex_flower_topology(radius=40.0)
    assert expected == {
        "n_endpoints": 0,
        "n_junctions_deg3": 12,
        "n_junctions_deg_ge4": 0,
        "n_edges": 18,
    }


def test_hexagonal_grid_measured_topology_matches_verified_junction_splitting():
    # Real skeletonization does not hit the ideal 12/18 above -- 2 of the
    # 12 true vertices render as a locally wider blob (3 unmitered
    # rectangle edges overlapping at a shallow angle) and split into a
    # pair of nodes ~1px apart, the same phenomenon
    # generate_double_t_junction demonstrates on purpose. Verified stable
    # across radius 40/60/80px (see synthetic.py's generate_hexagonal_grid
    # docstring) -- a rendering-geometry effect, not size-dependent noise,
    # so this asserts the actual reproducible value, not the ideal one.
    for radius in (40.0, 60.0, 80.0):
        size = int(radius * 7)
        gray = generate_hexagonal_grid(size=size, radius=radius, thickness=5)
        _, _, graph_result = _run_stage123(gray, spur_px=15.0)
        assert graph_result.n_endpoints == 0
        assert graph_result.n_junctions_deg_ge4 == 0
        assert graph_result.n_junctions_deg3 == 14
        assert graph_result.n_edges == 21


# -- generate_grid_with_flakes: flaking.py identification + area recovery ---


def test_flaking_recovers_known_circle_area_on_a_grid():
    n_lines, spacing, margin, thickness = 3, 70.0, 30.0, 5
    row_ys = [margin + spacing * (i + 1) for i in range(n_lines)]
    col_xs = row_ys
    flake_center = (row_ys[1], col_xs[1])
    flake_radius = 26.0

    gray = generate_grid_with_flakes(
        size=340, n_lines=n_lines, spacing=spacing, margin=margin, thickness=thickness,
        flake_centers=[flake_center], flake_radius=flake_radius,
    )
    _, skeleton_result, _ = _run_stage123(gray)
    flaking_result = exclude_flaking_regions(
        skeleton_result.mask_clean, skeleton_result.skel_image, skeleton_result.medial_radius,
    )

    true_flake_mask = np.zeros(gray.shape, dtype=bool)
    rr, cc = disk(flake_center, flake_radius, shape=gray.shape)
    true_flake_mask[rr, cc] = True
    true_flake_area_px2 = int(true_flake_mask.sum())

    assert len(flaking_result.candidates) == 1
    assert abs(flaking_result.excluded_area_px2 - true_flake_area_px2) / true_flake_area_px2 < 0.20


def test_flaking_finds_nothing_on_a_plain_grid_with_no_flakes():
    # Negative control: the same grid, no circles -- flaking.py must not
    # flag ordinary grid-crossing junction blobs as flaking candidates.
    gray = generate_grid(size=340, n_lines=3, spacing=70.0, margin=30.0, thickness=5)
    _, skeleton_result, _ = _run_stage123(gray)
    flaking_result = exclude_flaking_regions(
        skeleton_result.mask_clean, skeleton_result.skel_image, skeleton_result.medial_radius,
    )
    assert flaking_result.candidates == []
    assert flaking_result.excluded_area_px2 == 0
