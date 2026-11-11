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
    generate_hierarchical_network,
    generate_tapered_line,
    hierarchical_network_topology,
    tapered_line_ground_truth,
)
from src.crackgraph.synthetic_degradation import (
    apply_debris,
    apply_illumination_gradient,
    apply_jpeg_blocking,
)

FG_THRESHOLD = 100.0  # midpoint between fg_value=230 and bg_value=10 defaults


# -- tapered line (width + brightness taper at both tips) ------------------
#
# generate_tapered_line's width GEOMETRY is checked against a low threshold
# (just above bg_value=10), since that check is about the geometric taper,
# independent of the intensity fade -- whether a real Otsu threshold would
# clip the dim tips is a separate, deliberate effect these tests verify at
# the raw-pixel level, not something checked via an actual binarize() call
# (that's a later, pipeline-integration step).
GEOM_THRESHOLD = 10.5


def test_tapered_line_area_matches_trapezoid_formula():
    length, max_t, min_t = 200.0, 16.0, 0.0
    img = generate_tapered_line(length=length, max_thickness=max_t, min_thickness=min_t)
    mask = img > GEOM_THRESHOLD
    gt = tapered_line_ground_truth(length, max_t, min_t)
    # a few px of rasterization slack on a ~1800px2 double taper is
    # expected (mgrid-band rounding at the tapered boundary), not a
    # formula bug.
    assert mask.sum() == pytest.approx(gt["area_px2"], rel=0.05)


def test_tapered_line_width_narrows_toward_both_tips():
    img = generate_tapered_line(length=200.0, max_thickness=16.0, min_thickness=0.0, bearing_deg=0.0)
    mask = img > GEOM_THRESHOLD
    cols_with_fg = np.where(mask.any(axis=0))[0]
    x_lo, x_hi = int(cols_with_fg.min()), int(cols_with_fg.max())
    x_mid = (x_lo + x_hi) // 2
    left_widths = [int(mask[:, x].sum()) for x in np.linspace(x_lo + 2, x_mid, 4).astype(int)]
    right_widths = [int(mask[:, x].sum()) for x in np.linspace(x_mid, x_hi - 2, 4).astype(int)]
    # width should rise toward the midpoint from the left tip...
    assert all(left_widths[i] <= left_widths[i + 1] for i in range(len(left_widths) - 1))
    # ...and fall away from the midpoint toward the right tip -- both ends
    # taper, unlike the previous one-sided design.
    assert all(right_widths[i] >= right_widths[i + 1] for i in range(len(right_widths) - 1))
    assert left_widths[0] < left_widths[-1] and right_widths[0] > right_widths[-1]


def test_tapered_line_brightness_fades_toward_both_tips():
    img = generate_tapered_line(
        length=200.0, max_thickness=16.0, min_thickness=0.0, bearing_deg=0.0,
        fg_value=230.0, tip_value=60.0, bg_value=10.0,
    )
    mid_row = img.shape[0] // 2
    cols_with_fg = np.where((img[mid_row] > GEOM_THRESHOLD))[0]
    x_lo, x_hi = int(cols_with_fg.min()), int(cols_with_fg.max())
    x_mid = (x_lo + x_hi) // 2
    # sample along the centerline: brightness should rise from ~tip_value
    # at the left tip up to ~fg_value at the midpoint, matching the same
    # profile the width taper follows.
    left_vals = [img[mid_row, x] for x in np.linspace(x_lo + 1, x_mid, 5).astype(int)]
    right_vals = [img[mid_row, x] for x in np.linspace(x_mid, x_hi - 1, 5).astype(int)]
    assert left_vals[0] < left_vals[-1]
    assert right_vals[0] > right_vals[-1]
    assert left_vals[-1] == pytest.approx(230.0, abs=5.0)  # midpoint reads near fg_value
    assert left_vals[0] == pytest.approx(60.0, abs=15.0)  # tip reads near tip_value


def test_tapered_line_dim_tips_would_be_clipped_by_a_realistic_threshold():
    # The actual point of this generator: at a threshold in between
    # tip_value=60 and fg_value=230 (the same FG_THRESHOLD used for every
    # flat-fill case elsewhere in this file), the dim tips read as
    # background even though the geometric taper (checked at
    # GEOM_THRESHOLD, just above bg_value) extends further -- demonstrated
    # here at the raw-pixel level; whether the real binarize() (Otsu, not
    # a fixed threshold) reproduces this is a later pipeline-integration
    # step, not asserted here.
    img = generate_tapered_line(length=200.0, max_thickness=16.0, min_thickness=0.0)
    geom_mask = img > GEOM_THRESHOLD
    bright_mask = img > FG_THRESHOLD
    geom_cols = np.where(geom_mask.any(axis=0))[0]
    bright_cols = np.where(bright_mask.any(axis=0))[0]
    geom_span = geom_cols.max() - geom_cols.min()
    bright_span = bright_cols.max() - bright_cols.min()
    assert bright_span < geom_span, "a mid-range threshold should visibly truncate the dim tips"


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


def test_converging_lines_both_free_ends_taper_to_a_point():
    # Both free ends -- the back (non-merging) ends AND the joined
    # wedge's own far end -- should narrow to a point instead of ending
    # in a flat rectangular cut, at both the low-threshold geometric
    # extent (GEOM_THRESHOLD, matching case 1's convention) and using
    # width itself as the falsifiable signal.
    run_px, thickness, margin = 250.0, 12, 25.0
    img = generate_converging_lines(run_px=run_px, thickness=thickness, margin=margin, back_taper_px=25.0, front_taper_px=15.0)
    mask = img > GEOM_THRESHOLD
    x0 = int(margin)
    x1 = int(margin + run_px) - 1

    back_width = int(mask[:, x0 + 2].sum())
    back_width_full = int(mask[:, x0 + 30].sum())  # past the back taper zone
    assert 0 < back_width < back_width_full, "back ends should taper, not start at full width"

    front_width = int(mask[:, x1 - 1].sum())
    front_width_full = int(mask[:, x1 - 20].sum())  # just before the front taper zone
    assert 0 < front_width < front_width_full, "the joined wedge's far end should taper too, not cut off flat"


def test_converging_lines_ground_truth_rejects_non_crossing_params():
    with pytest.raises(ValueError):
        converging_lines_ground_truth(run_px=100.0, thickness=12, gap_start_px=5.0, gap_end_px=0.0, margin=10.0)


# -- hierarchical bimodal network -----------------------------------------


def test_hierarchical_network_adds_subbranches_without_disturbing_primary_layer():
    n_courses, spacing, margin, primary_thickness = 3, 140.0, 40.0, 12
    n_bricks_per_course = 3
    sub_branches_per_primary, sub_branch_length, sub_branch_thickness = 3, 25.0, 3
    size = 500

    # sub_branches_per_primary=0 isolates the primary brick-bond layer
    # alone (the stub loop's range() is empty, no division-by-zero risk),
    # replacing the old generate_grid-based comparison now that the
    # primary layer is brick-bond, not a rectilinear grid.
    base = generate_hierarchical_network(
        size=size, n_courses=n_courses, primary_spacing=spacing, margin=margin,
        primary_thickness=primary_thickness, n_bricks_per_course=n_bricks_per_course,
        sub_branches_per_primary=0,
    )
    full = generate_hierarchical_network(
        size=size, n_courses=n_courses, primary_spacing=spacing, margin=margin,
        primary_thickness=primary_thickness, n_bricks_per_course=n_bricks_per_course,
        sub_branch_thickness=sub_branch_thickness, sub_branch_length=sub_branch_length,
        sub_branches_per_primary=sub_branches_per_primary,
    )
    base_mask = base > FG_THRESHOLD
    full_mask = full > FG_THRESHOLD

    # sub-branches only add foreground pixels, never remove any of the
    # primary layer's own already-lit pixels.
    assert np.all(full_mask[base_mask])

    n_sub = n_courses * sub_branches_per_primary
    added_px = int(full_mask.sum()) - int(base_mask.sum())
    # each sub-branch starts AT the host course's own centerline (same
    # convention generate_t_junction/generate_double_t_junction already
    # use for their abutters), so part of its rectangle overlaps pixels
    # the primary layer already lit -- added_px is strictly less than the
    # naive non-overlapping n_sub*length*thickness upper bound, not equal
    # to it.
    upper_bound = n_sub * sub_branch_length * sub_branch_thickness
    assert 0 < added_px < upper_bound

    # each sub-branch's tip (near its far end, well past the primary
    # course's own thickness band) should be newly foreground in `full`
    # and background in `base` -- confirms the stubs actually reach their
    # expected far end, not just contribute overlap area near the host.
    row_ys = [margin + spacing * (i + 1) for i in range(n_courses)]
    x0, x1 = margin, size - margin
    span = x1 - x0
    # matches generate_hierarchical_network's own offset divisor (see its
    # comment) -- an unoffset divisor coincides with a staggered-row brick
    # joint at these defaults.
    fracs = [(k + 0.5) / (sub_branches_per_primary + 0.5) for k in range(sub_branches_per_primary)]
    for row_y in row_ys:
        for frac in fracs:
            x = x0 + frac * span
            tip_row = int(round(row_y - sub_branch_length + 2))
            xi = int(round(x))
            assert full_mask[tip_row, xi], "expected sub-branch tip to be foreground"
            assert not base_mask[tip_row, xi], "primary layer alone should not reach the tip"


def test_hierarchical_network_topology_is_brick_bond_t_junctions_only():
    # SPUR_PX_PLACEHOLDER = 15 (src/crackgraph/skeleton.py) is the actual
    # threshold sub-branch length is designed to straddle -- this test
    # only checks the PRE-PRUNING combinatorial formula (no pipeline
    # run), which does not itself depend on sub_branch_length at all
    # (it's still one T-junction per sub-branch either way, before any
    # pruning is applied). The real point of this test: a running-bond
    # brick pattern must produce ONLY T-junctions, never a 4-way crossing.
    n_courses, n_bricks_per_course, sub_branches_per_primary = 3, 3, 3

    # independent re-derivation, not calling hierarchical_network_topology's
    # own formula, to catch a copy-paste error in the brick-joint counting.
    n_v = (n_courses - 1) * (n_bricks_per_course - 1)
    n_sub = n_courses * sub_branches_per_primary
    expected = hierarchical_network_topology(n_courses, n_bricks_per_course, sub_branches_per_primary)
    assert expected["n_junctions_deg_ge4"] == 0, "brick bond must never produce a 4-way crossing"
    assert expected["n_junctions_deg3"] == 2 * n_v + n_sub
    assert expected["n_endpoints"] == 2 * n_courses + n_sub
    assert expected["n_edges"] == n_courses + 3 * n_v + 2 * n_sub
    # concrete numbers for this default (3 courses, 3 bricks/course, 3 subs/course):
    # n_v=4, n_sub=9 -> 0 deg>=4, 17 deg-3, 15 endpoints, 33 edges.
    assert (expected["n_junctions_deg_ge4"], expected["n_junctions_deg3"], expected["n_endpoints"], expected["n_edges"]) == (0, 17, 15, 33)


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
    # bleed-over. Measured directly across 5 seeds (not guessed): the
    # sparsest zone (5 segments) ranged 1.09-1.36x its naive upper bound --
    # small-n zones see proportionally more variance from both the random-
    # length draw and bleed, since there are fewer segments to average
    # over. BLEED_SLACK gives that a documented margin rather than
    # silently loosening the check to "whatever passes".
    BLEED_SLACK = 1.45
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


def test_density_gradient_field_segments_never_overlap():
    # Fixed (zero-variance) length isolates the no-overlap claim from
    # random-length sampling noise: with true non-overlap, measured area
    # must closely match each segment's own exact area (small
    # rasterization rounding only) -- if segments were allowed to overlap,
    # shared pixels would be counted once instead of twice, and measured
    # area would fall meaningfully short of this exact value. Each segment
    # is a spindle (tapered to a point at both ends, see
    # generate_density_gradient_field's own docstring for the derivation),
    # not a flat rectangle, so its true area is length*thickness*
    # (1 - tip_taper_frac/2), not the naive length*thickness.
    n_segments, length, thickness, tip_taper_frac = 15, 40.0, 6, 0.4
    img = generate_density_gradient_field(
        size=300, zone_bounds_frac=(0.0, 1.0), n_segments_per_zone=(n_segments,),
        thickness=thickness, length_range_px=(length, length), rng_seed=1,
        tip_taper_frac=tip_taper_frac,
    )
    mask = img > FG_THRESHOLD
    expected_area = n_segments * length * thickness * (1.0 - tip_taper_frac / 2.0)
    assert mask.sum() == pytest.approx(expected_area, rel=0.05)


def test_density_gradient_field_raises_when_zone_too_crowded():
    with pytest.raises(RuntimeError):
        generate_density_gradient_field(
            size=100, zone_bounds_frac=(0.0, 1.0), n_segments_per_zone=(200,),
            thickness=8, length_range_px=(30.0, 60.0), max_placement_attempts=20,
        )


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


def test_debris_punches_dark_specks_inside_existing_channels():
    # apply_debris models debris/charging that INTERRUPTS a crack channel
    # (dark specks punched into already-bright pixels), not new bright
    # material added elsewhere -- the opposite direction from the earlier
    # design, corrected to match "Channel Fragmentation" (splitting a
    # continuous crack into fragments), the actual failure mode this case
    # is meant to test.
    base = generate_hierarchical_network(sub_branch_length=25.0)
    out = apply_debris(base, n_specks=40, speck_radius_range_px=(1.0, 4.0), rng_seed=0)
    assert out.shape == base.shape
    base_mask = base > FG_THRESHOLD
    out_mask = out > FG_THRESHOLD
    # every pixel that changed must have STARTED as foreground (specks
    # only land inside existing channels, never on background) ...
    changed = out_mask != base_mask
    assert np.all(base_mask[changed]), "every darkened pixel should have been foreground in the clean base"
    # ...and the net effect is a REDUCTION in foreground area (holes
    # punched in), not an addition.
    assert out_mask.sum() < base_mask.sum(), "debris should remove foreground area, not add it"


def test_debris_raises_when_base_image_has_no_foreground():
    blank = np.full((50, 50), 10.0)
    with pytest.raises(ValueError):
        apply_debris(blank, n_specks=5)
