"""Correctness checks for the synthetic-benchmark-matrix generators added in
this step: generate_tapered_line, generate_converging_lines,
generate_hierarchical_network, generate_crescent_scale_pattern,
generate_density_gradient_field, plus the 3 composable degradation passes
in synthetic_degradation.py.

This step is deliberately geometry-only -- no binarize/skeletonize_and_prune/
extract_graph call anywhere in this file. Each test checks the raw
rasterized mask against its generator's own closed-form ground truth (the
crescent pattern is the one filled-shape exception -- see
generate_crescent_scale_pattern's own docstring for why). Wiring these
through the real pipeline and comparing measured-vs-expected is a later,
separate step (see the synthetic-benchmark plan) -- not done here.
"""

import math

import numpy as np
import pytest

from src.crackgraph.synthetic import (
    _crescent_mask,
    converging_lines_ground_truth,
    crescent_ground_truth,
    density_gradient_ground_truth,
    generate_converging_lines,
    generate_crescent_scale_pattern,
    generate_density_gradient_field,
    generate_grid,
    generate_hierarchical_network,
    generate_tapered_line,
    grid_topology,
    hierarchical_network_topology,
    tapered_line_ground_truth,
)
from src.crackgraph.synthetic_degradation import (
    apply_debris,
    apply_illumination_gradient,
    apply_jpeg_blocking,
)

FG_THRESHOLD = 100.0  # midpoint between fg_value=230 and bg_value=10 defaults


# -- tapered line -------------------------------------------------------


def test_tapered_line_area_matches_trapezoid_formula():
    length, t_start, t_end = 200.0, 16.0, 2.0
    img = generate_tapered_line(length=length, thickness_start=t_start, thickness_end=t_end)
    mask = img > FG_THRESHOLD
    gt = tapered_line_ground_truth(length, t_start, t_end)
    # a few px of rasterization slack on a ~1800px2 trapezoid is expected
    # (polygon-fill rounding at the tapered boundary), not a formula bug.
    assert mask.sum() == pytest.approx(gt["area_px2"], rel=0.05)


def test_tapered_line_width_narrows_monotonically():
    img = generate_tapered_line(length=200.0, thickness_start=16.0, thickness_end=2.0, bearing_deg=0.0)
    mask = img > FG_THRESHOLD
    cols_with_fg = np.where(mask.any(axis=0))[0]
    x_lo, x_hi = int(cols_with_fg.min()), int(cols_with_fg.max())
    xs = np.linspace(x_lo + 2, x_hi - 2, 6).astype(int)
    widths = [int(mask[:, x].sum()) for x in xs]
    assert all(widths[i] >= widths[i + 1] for i in range(len(widths) - 1))
    assert widths[0] > widths[-1]  # genuinely tapers, not flat


# -- converging parallel lines -------------------------------------------


def _column_is_merged(col: np.ndarray) -> bool:
    """True if the column's foreground pixels form one contiguous run (no
    background gap inside their own row-span) -- i.e. the two bands have
    merged into one connected shape at this column."""
    fg_rows = np.where(col)[0]
    if fg_rows.size == 0:
        return False
    span = col[fg_rows.min() : fg_rows.max() + 1]
    return bool(span.all())


def test_converging_lines_merge_transition_matches_closed_form():
    run_px, thickness, gap_start, gap_end, margin = 250.0, 12, 60.0, 0.0, 25.0
    img = generate_converging_lines(
        run_px=run_px, thickness=thickness, gap_start_px=gap_start,
        gap_end_px=gap_end, margin=margin,
    )
    mask = img > FG_THRESHOLD
    gt = converging_lines_ground_truth(run_px, thickness, gap_start, gap_end, margin)
    x_touch = gt["x_touch_px"]

    x_before = int(x_touch - 30)
    x_after = int(x_touch + 30)
    assert not _column_is_merged(mask[:, x_before]), "expected two separate bands well before x_touch"
    assert _column_is_merged(mask[:, x_after]), "expected one merged wedge well after x_touch"


def test_converging_lines_ground_truth_rejects_non_crossing_params():
    with pytest.raises(ValueError):
        converging_lines_ground_truth(run_px=100.0, thickness=12, gap_start_px=5.0, gap_end_px=0.0, margin=10.0)


# -- hierarchical bimodal network -----------------------------------------


def test_hierarchical_network_adds_subbranches_without_disturbing_primary_grid():
    n_primary_lines, spacing, margin, primary_thickness = 2, 160.0, 40.0, 12
    sub_branches_per_primary, sub_branch_length, sub_branch_thickness = 3, 25.0, 3
    size = 500

    base = generate_grid(
        size=size, n_lines=n_primary_lines, spacing=spacing, margin=margin, thickness=primary_thickness,
    )
    full = generate_hierarchical_network(
        size=size, n_primary_lines=n_primary_lines, primary_spacing=spacing, margin=margin,
        primary_thickness=primary_thickness, sub_branch_thickness=sub_branch_thickness,
        sub_branch_length=sub_branch_length, sub_branches_per_primary=sub_branches_per_primary,
    )
    base_mask = base > FG_THRESHOLD
    full_mask = full > FG_THRESHOLD

    # sub-branches only add foreground pixels, never remove any of the
    # primary grid's own already-lit pixels.
    assert np.all(full_mask[base_mask])

    n_sub = n_primary_lines * sub_branches_per_primary
    added_px = int(full_mask.sum()) - int(base_mask.sum())
    # each sub-branch starts AT the host line's own centerline (same
    # convention generate_t_junction/generate_double_t_junction already
    # use for their abutters), so part of its rectangle overlaps pixels
    # the primary grid already lit -- added_px is strictly less than the
    # naive non-overlapping n_sub*length*thickness upper bound, not equal
    # to it.
    upper_bound = n_sub * sub_branch_length * sub_branch_thickness
    assert 0 < added_px < upper_bound

    # each sub-branch's tip (near its far end, well past the primary
    # line's own thickness band) should be newly foreground in `full` and
    # background in `base` -- confirms the stubs actually reach their
    # expected far end, not just contribute overlap area near the host.
    row_ys = [margin + spacing * (i + 1) for i in range(n_primary_lines)]
    x0, x1 = margin, size - margin
    span = x1 - x0
    fracs = [(k + 0.5) / sub_branches_per_primary for k in range(sub_branches_per_primary)]
    for row_y in row_ys:
        for frac in fracs:
            x = x0 + frac * span
            tip_row = int(round(row_y - sub_branch_length + 2))
            xi = int(round(x))
            assert full_mask[tip_row, xi], "expected sub-branch tip to be foreground"
            assert not base_mask[tip_row, xi], "primary grid alone should not reach the tip"


def test_hierarchical_network_topology_formula_straddles_spur_threshold():
    # SPUR_PX_PLACEHOLDER = 15 (src/crackgraph/skeleton.py) is the actual
    # threshold this case is designed to straddle -- this test only checks
    # the PRE-PRUNING combinatorial formula (no pipeline run), which does
    # not itself depend on sub_branch_length at all (it's still one T-
    # junction per sub-branch either way, before any pruning is applied).
    n_primary_lines, sub_branches_per_primary = 2, 3
    base_grid = grid_topology(n_primary_lines, n_primary_lines)
    n_sub = n_primary_lines * sub_branches_per_primary

    expected = hierarchical_network_topology(n_primary_lines, sub_branches_per_primary)
    assert expected["n_junctions_deg_ge4"] == base_grid["n_junctions_deg_ge4"]
    assert expected["n_junctions_deg3"] == n_sub
    assert expected["n_endpoints"] == base_grid["n_endpoints"] + n_sub
    assert expected["n_edges"] == base_grid["n_edges"] + 2 * n_sub
    # concrete numbers for this default (2x2 primary grid, 3 subs/line):
    # 4 deg>=4 junctions, 6 deg-3 junctions, 14 endpoints, 24 edges.
    assert (expected["n_junctions_deg_ge4"], expected["n_junctions_deg3"], expected["n_endpoints"], expected["n_edges"]) == (4, 6, 14, 24)


# -- crescent-scale pattern (filled disk-minus-disk geometry) -------------


def test_crescent_ground_truth_area_matches_pixel_measurement():
    radius, offset = 70.0, 45.0
    mask = _crescent_mask((300, 300), (150.0, 130.0), radius, offset)
    gt = crescent_ground_truth(radius, offset)
    # a few px of rasterization slack at the two sharp cusps (a single-
    # pixel-wide tip is inherently ambiguous under a >= boundary test),
    # not a formula bug.
    assert int(mask.sum()) == pytest.approx(gt["area_px2"], rel=0.02)


def test_crescent_ground_truth_perimeter_is_offset_invariant():
    radius = 70.0
    # Independent re-derivation (not calling crescent_ground_truth's own
    # formula) across a spread of offsets, to catch a copy-paste error in
    # the "outer + inner arc angles always sum to 2*pi" claim.
    for offset in (5.0, 30.0, 45.0, 90.0, 130.0):
        alpha = math.acos(offset / (2.0 * radius))
        outer_arc_angle = 2.0 * math.pi - 2.0 * alpha
        inner_arc_angle = 2.0 * alpha
        expected_perimeter = radius * (outer_arc_angle + inner_arc_angle)
        assert expected_perimeter == pytest.approx(2.0 * math.pi * radius, rel=1e-9)
        assert crescent_ground_truth(radius, offset)["perimeter_px"] == pytest.approx(
            expected_perimeter, rel=1e-9
        )


def test_crescent_ground_truth_rejects_degenerate_offset():
    with pytest.raises(ValueError):
        crescent_ground_truth(radius=70.0, offset=0.0)
    with pytest.raises(ValueError):
        crescent_ground_truth(radius=70.0, offset=200.0)  # >= 2*radius


def test_crescent_scale_pattern_tiles_touch_into_one_connected_network():
    from scipy.ndimage import label

    img = generate_crescent_scale_pattern(n_rows=4, n_cols=4)
    mask = img > FG_THRESHOLD
    labeled, _ = label(mask)
    sizes = np.bincount(labeled.ravel())[1:]  # drop background label 0
    largest_fraction = sizes.max() / mask.sum()
    # a genuine fish-scale tiling merges most/all tiles into one touching
    # network -- isolated, non-touching crescents would instead show up as
    # 16 similarly-sized separate components (one per tile), so a small
    # largest_fraction would mean the tiles aren't actually touching.
    assert largest_fraction > 0.5


# -- non-uniform density field ---------------------------------------------


def test_density_gradient_field_zone_areas_below_upper_bound_and_ordered():
    n_segments_per_zone = (60, 20, 5)
    length_range_px = (30.0, 60.0)
    thickness = 8
    zone_bounds_frac = (0.0, 0.33, 0.67, 1.0)
    size = 500

    img = generate_density_gradient_field(
        size=size, zone_bounds_frac=zone_bounds_frac, n_segments_per_zone=n_segments_per_zone,
        thickness=thickness, length_range_px=length_range_px, rng_seed=0,
    )
    mask = img > FG_THRESHOLD
    gt = density_gradient_ground_truth(n_segments_per_zone, length_range_px, thickness)

    # Segments are placed by CENTER within a zone's column bounds but have
    # real physical length in a random bearing, so a segment centered near
    # a zone boundary can extend into the neighboring zone -- a column-
    # sliced per-zone area measurement is therefore contaminated by this
    # bleed-over and can exceed the naive non-overlap upper bound by a
    # measured ~5-11% at this size/segment-count (verified directly, not
    # guessed); BLEED_SLACK gives that a documented margin rather than
    # silently loosening the check to "whatever passes".
    BLEED_SLACK = 1.25
    zone_areas = []
    for zi in range(len(n_segments_per_zone)):
        col_lo = int(zone_bounds_frac[zi] * size)
        col_hi = int(zone_bounds_frac[zi + 1] * size)
        area = int(mask[:, col_lo:col_hi].sum())
        zone_areas.append(area)
        assert area <= gt["upper_bound_area_px2_per_zone"][zi] * BLEED_SLACK

    assert zone_areas[0] > zone_areas[1] > zone_areas[2], "density should strictly decrease left to right"


def test_density_gradient_field_rejects_mismatched_zone_bounds():
    with pytest.raises(ValueError):
        generate_density_gradient_field(zone_bounds_frac=(0.0, 0.5, 1.0), n_segments_per_zone=(10, 10, 10))


# -- degradation passes (synthetic_degradation.py) --------------------------
#
# None of these have a closed-form ground truth for their degraded pixel
# values (lossy or randomized by construction -- see synthetic_degradation.py's
# module docstring), so these tests check pipeline-agnostic invariants
# (shape, value range, "something actually changed") rather than an
# expected-vs-measured comparison.


def test_illumination_gradient_runs_and_preserves_shape_and_range():
    base = generate_converging_lines()
    out = apply_illumination_gradient(base, direction_deg=0.0, amplitude=60.0)
    assert out.shape == base.shape
    assert out.min() >= 0.0 and out.max() <= 255.0
    left_mean = out[:, : out.shape[1] // 4].mean()
    right_mean = out[:, -out.shape[1] // 4 :].mean()
    assert left_mean != pytest.approx(right_mean, abs=0.5), "a genuine gradient should differ side to side"


def test_jpeg_blocking_runs_and_preserves_shape_and_range():
    base = generate_hierarchical_network(sub_branch_length=25.0)
    out = apply_jpeg_blocking(base, quality=15)
    assert out.shape == base.shape
    assert out.min() >= 0.0 and out.max() <= 255.0
    assert not np.array_equal(out, base), "a real lossy round-trip should change at least some pixels"


def test_debris_adds_specks_without_removing_existing_foreground():
    base = generate_hierarchical_network(sub_branch_length=25.0)
    out = apply_debris(base, n_specks=40, speck_radius_range_px=(1.0, 4.0), rng_seed=0)
    assert out.shape == base.shape
    base_mask = base > FG_THRESHOLD
    out_mask = out > FG_THRESHOLD
    assert np.all(out_mask[base_mask]), "debris should only add foreground, never remove existing cracks"
    assert out_mask.sum() > base_mask.sum(), "specks should actually add some new foreground"
