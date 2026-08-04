"""Correctness checks for the synthetic-benchmark-matrix generators added in
this step: generate_tapered_line, generate_converging_lines,
generate_hierarchical_network, generate_crescent_mesh,
generate_density_gradient_field.

This step is deliberately geometry-only -- no binarize/skeletonize_and_prune/
extract_graph call anywhere in this file. Each test checks the raw
rasterized mask (or, for the crescent mesh, the shared _draw_arc_band
helper directly) against its generator's own closed-form ground truth.
Wiring these through the real pipeline and comparing measured-vs-expected
is a later, separate step (see the synthetic-benchmark plan) -- not done
here.
"""

import math

import numpy as np
import pytest

from src.crackgraph.synthetic import (
    _draw_arc_band,
    arc_tortuosity_ground_truth,
    converging_lines_ground_truth,
    density_gradient_ground_truth,
    generate_converging_lines,
    generate_crescent_mesh,
    generate_density_gradient_field,
    generate_grid,
    generate_hierarchical_network,
    generate_tapered_line,
    grid_topology,
    hierarchical_network_topology,
    tapered_line_ground_truth,
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


# -- crescent mesh (arc-band geometry + tortuosity formula) ---------------


def test_arc_tortuosity_ground_truth_matches_independent_half_arc_formula():
    # Independent re-derivation (not calling arc_tortuosity_ground_truth's
    # own code path) of the same closed form for a few known angles, to
    # catch a copy-paste error in the full-vs-half-arc phi convention.
    for half_angle_deg in (10.0, 40.0, 75.0, 89.0):
        phi = math.radians(2.0 * half_angle_deg)
        expected = phi / (2.0 * math.sin(phi / 2.0))
        assert arc_tortuosity_ground_truth(half_angle_deg) == pytest.approx(expected, rel=1e-9)
    # sanity bounds: tortuosity is exactly 1 in the zero-angle limit and
    # strictly increasing with angle over (0, 180) deg.
    assert arc_tortuosity_ground_truth(0.001) == pytest.approx(1.0, abs=1e-4)
    values = [arc_tortuosity_ground_truth(a) for a in (10.0, 40.0, 75.0, 89.0)]
    assert all(values[i] < values[i + 1] for i in range(len(values) - 1))


def test_arc_band_pixels_match_independent_trig_ring_and_sector():
    size = 400
    center_rc = (50.0, 200.0)
    radius = 200.0
    half_angle = 40.0
    thickness = 12
    img = np.full((size, size), 10.0)
    _draw_arc_band(img, center_rc, radius, half_angle, thickness, 230.0)
    mask = img > FG_THRESHOLD

    # points computed from independent trig (row = row_c + d*cos(phi),
    # col = col_c + d*sin(phi), matching arctan2(coldelta, rowdelta)'s own
    # convention derived by hand, not by re-reading _draw_arc_band's array
    # code) should be foreground when on the ring and inside the sector.
    for phi_deg in (-35.0, -20.0, 0.0, 20.0, 35.0):
        phi = math.radians(phi_deg)
        row = center_rc[0] + radius * math.cos(phi)
        col = center_rc[1] + radius * math.sin(phi)
        assert mask[int(round(row)), int(round(col))], f"expected foreground at phi={phi_deg}"

    # well outside the ring radius (same phi=0 direction) -> background
    row_out = center_rc[0] + radius + 3 * thickness
    col_out = center_rc[1]
    assert not mask[int(round(row_out)), int(round(col_out))]

    # on the ring but well outside the +/-half_angle sector -> background
    phi_out = math.radians(half_angle + 15.0)
    row_sector_out = center_rc[0] + radius * math.cos(phi_out)
    col_sector_out = center_rc[1] + radius * math.sin(phi_out)
    assert not mask[int(round(row_sector_out)), int(round(col_sector_out))]


def test_crescent_mesh_renders_n_arcs_and_zero_crossbars_cleanly():
    # n_crossbars=0 isolates pure arc geometry (no vertical bars) so this
    # step's raw-gallery image can show the arcs on their own if desired.
    img = generate_crescent_mesh(n_arcs=3, n_crossbars=0)
    mask = img > FG_THRESHOLD
    assert mask.any()
    # 3 arcs stacked with positive arc_spacing should produce foreground
    # spread across a wider row range than a single arc would.
    fg_rows = np.where(mask.any(axis=1))[0]
    assert fg_rows.max() - fg_rows.min() > 100


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
