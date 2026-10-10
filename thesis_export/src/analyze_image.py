"""CLI entry point: run stage 1-3 on a single image.

Usage:
    python3 -m src.analyze_image <image_path> [options]

For now this always analyzes only a top-left corner crop of the image
(see crackgraph/region.py) unless --full-image is passed -- full-image
runs are deferred until this corner check is validated (see README).
"""

import argparse
from pathlib import Path

import numpy as np
import skan
import skimage

from .crackgraph.anisotropy import ORIENT_WINDOW_PX_PLACEHOLDER, compute_anisotropy
from .crackgraph.binarize import binarize
from .crackgraph.corners import (
    CORNER_MIN_TURN_DEG,
    CORNER_SEARCH_RADIUS_PX,
    CORNER_WINDOW_PX,
    cross_check_junctions,
    find_background_contours,
)
from .crackgraph.curvature import CURVATURE_WINDOW_PX_PLACEHOLDER, compute_edge_curvature
from .crackgraph.edge_metrics import (
    AREA_JUNCTION_BLOB_RADIUS_PLACEHOLDER,
    WIDTH_TRIM_INNER_PX_PLACEHOLDER,
    compute_edge_metrics,
    write_edge_metrics_csv,
)
from .crackgraph.flaking import exclude_flaking_regions
from .crackgraph.graph import extract_graph
from .crackgraph.io_utils import load_image
from .crackgraph.junctions import (
    ANNULUS_INNER_PX_PLACEHOLDER,
    ANNULUS_OUTER_PX_PLACEHOLDER,
    T_RIGHT_TOL_DEG_PLACEHOLDER,
    T_STRAIGHT_TOL_DEG_PLACEHOLDER,
    Y_ANGLE_TOL_DEG_PLACEHOLDER,
    classify_junctions,
)
from .crackgraph.overlay import render_overlay, render_precedence_overlay
from .crackgraph.precedence import build_precedence_graph
from .crackgraph.region import default_corner_crop
from .crackgraph.skeleton import CORR_THRESHOLD, SPUR_PX_PLACEHOLDER, skeletonize_and_prune
from .crackgraph.xlsx_report import (
    anisotropy_classification,
    append_chunk_to_workbook,
    corner_agreement_counts,
    curvature_stats,
    tortuosity_stats,
)

# Derived from the 31 real Keyence Vorbeladung captures in data/raw/ as of this
# writing (width 7254-7434 px, height 7526-7679 px), rounded generously. One
# outlier (humidity_loading_ptfe/23RH_PTFE_v1_mm000001.jpg, 4429x3322 px) was
# excluded -- a visibly different aspect ratio/size, i.e. exactly the kind of
# "wrong image type" case this check exists to catch.
EXPECTED_WIDTH_PX_RANGE = (7000, 7700)
EXPECTED_HEIGHT_PX_RANGE = (7300, 7900)


def parse_args():
    p = argparse.ArgumentParser(description="Stage 1-3 crack-graph pipeline (single image).")
    p.add_argument("image_path", type=str)
    p.add_argument("--out-dir", type=str, default="outputs")
    p.add_argument(
        "--xlsx-out",
        type=str,
        default=None,
        help=(
            "Append this run's results as a row to the given .xlsx workbook "
            "(one sheet per image, one row per chunk). Off by default."
        ),
    )
    p.add_argument("--spur-px", type=float, default=SPUR_PX_PLACEHOLDER)
    p.add_argument("--corner-artifact-corr-threshold", type=float, default=CORR_THRESHOLD)
    p.add_argument("--min-object-px", type=int, default=4)
    p.add_argument("--max-overlay-dim", type=int, default=2500)
    p.add_argument("--otsu-sanity-band", type=float, nargs=2, default=(0.01, 0.15))
    p.add_argument("--corner-frac", type=float, default=0.125)
    p.add_argument("--edge-margin-frac", type=float, default=0.02)
    p.add_argument("--annulus-inner-px", type=float, default=ANNULUS_INNER_PX_PLACEHOLDER)
    p.add_argument("--annulus-outer-px", type=float, default=ANNULUS_OUTER_PX_PLACEHOLDER)
    p.add_argument("--curvature-window-px", type=float, default=CURVATURE_WINDOW_PX_PLACEHOLDER)
    p.add_argument("--orientation-window-px", type=float, default=ORIENT_WINDOW_PX_PLACEHOLDER)
    p.add_argument("--y-angle-tol-deg", type=float, default=Y_ANGLE_TOL_DEG_PLACEHOLDER)
    p.add_argument("--t-straight-tol-deg", type=float, default=T_STRAIGHT_TOL_DEG_PLACEHOLDER)
    p.add_argument("--t-right-tol-deg", type=float, default=T_RIGHT_TOL_DEG_PLACEHOLDER)
    p.add_argument("--corner-search-radius-px", type=float, default=CORNER_SEARCH_RADIUS_PX)
    p.add_argument("--corner-window-px", type=float, default=CORNER_WINDOW_PX)
    p.add_argument("--corner-min-turn-deg", type=float, default=CORNER_MIN_TURN_DEG)
    p.add_argument("--width-trim-inner-px", type=float, default=WIDTH_TRIM_INNER_PX_PLACEHOLDER)
    p.add_argument("--area-ambiguity-radius-px", type=float, default=AREA_JUNCTION_BLOB_RADIUS_PLACEHOLDER)
    p.add_argument(
        "--full-image",
        action="store_true",
        default=False,
        help="Process the whole image instead of the default corner crop (not used yet, see README).",
    )
    p.add_argument(
        "--show-fit-detail",
        action="store_true",
        default=False,
        help=(
            "Also write a second overlay with the fitted-curve/tick/terminal-segment "
            "diagnostic layer and full angle-gap labels, for auditing the angle estimator. "
            "The default (clean) overlay is always written regardless."
        ),
    )
    p.add_argument(
        "--hide-corner-check",
        action="store_true",
        default=False,
        help=(
            "Omit corner cross-check markers/diamonds from the overlay(s). The cross-check "
            "itself still runs and still appears in the console report -- this only hides "
            "the markers."
        ),
    )
    p.add_argument(
        "--skip-curvature",
        action="store_true",
        default=False,
        help="Don't compute edge curvature/tortuosity. Independent of every other stage.",
    )
    p.add_argument(
        "--skip-anisotropy",
        action="store_true",
        default=False,
        help="Don't compute network anisotropy. Independent of every other stage.",
    )
    p.add_argument(
        "--skip-junctions",
        action="store_true",
        default=False,
        help=(
            "Don't classify junctions (stage 4). Cascades: corner cross-check and the "
            "precedence graph both need junction classification, so this skips them too."
        ),
    )
    p.add_argument(
        "--skip-corner-cross-check",
        action="store_true",
        default=False,
        help=(
            "Don't compute the corner cross-check (the background-contour method), unlike "
            "--hide-corner-check, which still computes it but only hides its overlay markers. "
            "The precedence graph still runs if requested, using the tangent-fit method alone."
        ),
    )
    p.add_argument(
        "--skip-precedence",
        action="store_true",
        default=False,
        help="Don't build or render the precedence graph (stage 5).",
    )
    args = p.parse_args()
    skip_flags_set = args.skip_curvature or args.skip_anisotropy or (
        args.skip_junctions or args.skip_corner_cross_check or args.skip_precedence
    )
    if args.xlsx_out is not None and skip_flags_set:
        p.error("--xlsx-out requires the full pipeline; it can't be combined with any --skip-* flag.")
    return args


def main():
    args = parse_args()
    image_path = Path(args.image_path)
    gray_full, rgb_full = load_image(image_path)
    full_h, full_w = gray_full.shape

    if not (
        EXPECTED_WIDTH_PX_RANGE[0] <= full_w <= EXPECTED_WIDTH_PX_RANGE[1]
        and EXPECTED_HEIGHT_PX_RANGE[0] <= full_h <= EXPECTED_HEIGHT_PX_RANGE[1]
    ):
        print(
            f"[WARNING] image is {full_w} x {full_h} px; expected roughly "
            f"{EXPECTED_WIDTH_PX_RANGE[0]}-{EXPECTED_WIDTH_PX_RANGE[1]} x "
            f"{EXPECTED_HEIGHT_PX_RANGE[0]}-{EXPECTED_HEIGHT_PX_RANGE[1]} px for a "
            "5mm Keyence Vorbeladung capture -- check you're using the right image type."
        )

    if args.full_image:
        gray, rgb = gray_full, rgb_full
        region_desc = f"full image, {full_w} x {full_h} px"
        stem_suffix = "full"
    else:
        region = default_corner_crop(
            full_h,
            full_w,
            corner_frac=args.corner_frac,
            edge_margin_frac=args.edge_margin_frac,
        )
        gray = gray_full[region.row_slice, region.col_slice]
        rgb = rgb_full[region.row_slice, region.col_slice]
        crop_h, crop_w = gray.shape
        region_desc = (
            f"top-left corner, {crop_w} x {crop_h} px "
            f"[corner-frac={region.corner_frac}, edge-margin-frac={region.edge_margin_frac}]"
        )
        stem_suffix = "corner"

    binarize_result = binarize(gray, sanity_band=tuple(args.otsu_sanity_band))

    # Scout pass: skeletonize the raw mask only to get a width signal
    # (medial_radius) for flaking identification -- not necessarily the
    # final skeleton used below. See crackgraph/flaking.py.
    scout_skeleton_result = skeletonize_and_prune(
        binarize_result.mask,
        source_image=gray,
        min_object_px=args.min_object_px,
        spur_px=args.spur_px,
        corner_artifact_corr_threshold=args.corner_artifact_corr_threshold,
    )
    flaking_result = exclude_flaking_regions(
        scout_skeleton_result.mask_clean,
        scout_skeleton_result.skel_image,
        scout_skeleton_result.medial_radius,
    )
    if flaking_result.candidates:
        # Real pass: re-skeletonize on the corrected mask so flaked
        # regions never reach the thinning step at all -- not "ignored",
        # genuinely treated as dark/background, same as any other pixel
        # skeletonize_and_prune was never told is foreground.
        skeleton_result = skeletonize_and_prune(
            flaking_result.mask_corrected,
            source_image=gray,
            min_object_px=args.min_object_px,
            spur_px=args.spur_px,
            corner_artifact_corr_threshold=args.corner_artifact_corr_threshold,
        )
    else:
        skeleton_result = scout_skeleton_result
    graph_result = extract_graph(skeleton_result.skeleton)
    curvature_result = None
    if not args.skip_curvature:
        curvature_result = compute_edge_curvature(
            skeleton_result.skeleton,
            graph_result,
            window_px=args.curvature_window_px,
        )
    anisotropy_result = None
    if not args.skip_anisotropy:
        anisotropy_result = compute_anisotropy(
            skeleton_result.skeleton,
            graph_result,
            window_px=args.orientation_window_px,
        )
    edge_metrics_result = compute_edge_metrics(
        skeleton_result.skeleton,
        graph_result,
        skeleton_result.mask_clean,
        skeleton_result.medial_radius,
        width_trim_inner_px=args.width_trim_inner_px,
        area_ambiguity_radius_px=args.area_ambiguity_radius_px,
    )
    junction_result = None
    if not args.skip_junctions:
        junction_result = classify_junctions(
            skeleton_result.skeleton,
            graph_result,
            inner_radius_px=args.annulus_inner_px,
            outer_radius_px=args.annulus_outer_px,
            y_angle_tol_deg=args.y_angle_tol_deg,
            t_straight_tol_deg=args.t_straight_tol_deg,
            t_right_tol_deg=args.t_right_tol_deg,
            medial_radius=skeleton_result.medial_radius,
        )
    # Corner cross-check needs a real junction_result to check against; skipping
    # junction classification skips this too, regardless of --skip-corner-cross-check.
    corner_check_skipped = args.skip_corner_cross_check or junction_result is None
    corner_cross_check = []
    if not corner_check_skipped:
        background_contours = find_background_contours(skeleton_result.mask_clean)
        corner_cross_check = cross_check_junctions(
            junction_result,
            background_contours,
            search_radius_px=args.corner_search_radius_px,
            window_px=args.corner_window_px,
            min_turn_deg=args.corner_min_turn_deg,
            y_angle_tol_deg=args.y_angle_tol_deg,
            t_straight_tol_deg=args.t_straight_tol_deg,
            t_right_tol_deg=args.t_right_tol_deg,
        )
    # Precedence needs a real junction_result too; corner_cross_check may be the
    # empty list above (either genuinely skipped or genuinely no findings) -- either
    # way build_precedence_graph degrades cleanly to tangent-fit-only arcs on [].
    precedence_skipped = args.skip_precedence or junction_result is None
    precedence_result = None
    if not precedence_skipped:
        precedence_result = build_precedence_graph(
            junction_result,
            corner_cross_check,
            y_angle_tol_deg=args.y_angle_tol_deg,
            t_straight_tol_deg=args.t_straight_tol_deg,
            t_right_tol_deg=args.t_right_tol_deg,
        )

    # Nest under the image's own source folder (e.g. data/raw/T5,
    # data/raw/humidity_loading) so outputs from different coatings/sample
    # batches don't pile up flat in one directory.
    out_dir = Path(args.out_dir) / image_path.parent.name
    out_dir.mkdir(parents=True, exist_ok=True)
    edge_metrics_csv_path = out_dir / f"{image_path.stem}_{stem_suffix}_edge_metrics.csv"
    write_edge_metrics_csv(edge_metrics_result, edge_metrics_csv_path)
    precedence_out_path = out_dir / f"{image_path.stem}_{stem_suffix}_precedence.png"
    if precedence_result is not None:
        render_precedence_overlay(
            rgb,
            skeleton_result.skeleton,
            graph_result,
            precedence_result,
            skeleton_result.medial_radius,
            precedence_out_path,
            max_overlay_dim=args.max_overlay_dim,
        )
    else:
        precedence_out_path = None
    overlay_corner_cross_check = None if args.hide_corner_check else corner_cross_check

    out_path = out_dir / f"{image_path.stem}_{stem_suffix}_overlay.png"
    scale = render_overlay(
        rgb,
        skeleton_result.skeleton,
        graph_result,
        out_path,
        max_overlay_dim=args.max_overlay_dim,
        junction_result=junction_result,
        corner_cross_check=overlay_corner_cross_check,
        detail=False,
    )
    detail_out_path = None
    if args.show_fit_detail:
        detail_out_path = out_dir / f"{image_path.stem}_{stem_suffix}_overlay_detail.png"
        render_overlay(
            rgb,
            skeleton_result.skeleton,
            graph_result,
            detail_out_path,
            max_overlay_dim=args.max_overlay_dim,
            junction_result=junction_result,
            corner_cross_check=overlay_corner_cross_check,
            detail=True,
        )

    print(f"=== Stage 1-3 report: {image_path.name} ===")
    print(f"Image (full):     {full_w} x {full_h} px, RGB")
    print(f"Region analyzed:  {region_desc}")
    if not args.full_image:
        print("                  (full-image run skipped for now -- pass --full-image to override)")
    print()
    print("-- Parameters (every value used, for reproducing this exact report) --")
    for name, value in vars(args).items():
        print(f"  --{name.replace('_', '-')} = {value}")
    print(f"  library versions: numpy={np.__version__}, skimage={skimage.__version__}, skan={skan.__version__}")
    print()
    print("-- Stage 1: Binarize --")
    print(f"Threshold value:        {binarize_result.threshold:.2f}        [measured]")
    print(f"Foreground fraction:    {binarize_result.foreground_fraction * 100:.2f}%     [measured]")
    band = binarize_result.sanity_band
    status = "PASS" if binarize_result.sanity_ok else "FAIL"
    print(
        f"Sanity check:           {status} "
        f"(expected band {band[0] * 100:.0f}-{band[1] * 100:.0f}%)   [interpreted]"
    )
    if not binarize_result.sanity_ok:
        print(
            f"[WARNING] foreground fraction {binarize_result.foreground_fraction * 100:.2f}% "
            "is outside the expected band -- inspect the threshold/mask before trusting "
            "downstream counts."
        )
    print()
    print("-- Flaking/delamination exclusion (see crackgraph/flaking.py) --")
    print(
        f"Reference crack width (this image, skeleton-median): "
        f"{flaking_result.reference_width_px:.1f} px    [measured]"
    )
    print(
        f"Candidates found: {len(flaking_result.candidates)}    "
        "[interpreted -- width+solidity flagged, not junction-blob-filtered yet]"
    )
    for c in flaking_result.candidates:
        print(f"  area={c.area_px2} px2  solidity={c.solidity:.3f}  bbox={c.bbox}")
    print(
        f"Excluded area: {flaking_result.excluded_area_px2} px2 "
        f"({flaking_result.excluded_area_pct:.3f}% of image)    [measured]"
    )
    if flaking_result.candidates:
        print(
            "Mask corrected and re-skeletonized (second pass) -- excluded pixels treated as "
            "background, not folded into crack area/width/length."
        )
    print()
    print("-- Stage 2: Skeletonize + prune --")
    print(
        f"Skeleton pixel count (pre/post-prune): "
        f"{skeleton_result.n_pixels_pre_prune}/{skeleton_result.n_pixels_post_prune}   [measured]"
    )
    print(
        f"Spur length threshold:   {skeleton_result.spur_px_threshold} px    "
        "[PLACEHOLDER -- not calibrated to real h/um-per-px]"
    )
    example_spurs = [round(x, 1) for x in skeleton_result.pruned_spur_lengths[:5]]
    print(f"Spurs pruned: {skeleton_result.n_spurs_pruned}, example lengths: {example_spurs}   [measured]")
    example_fragments = [round(x, 1) for x in skeleton_result.pruned_fragment_lengths[:5]]
    print(
        f"Isolated fragments pruned: {skeleton_result.n_fragments_pruned}, "
        f"example lengths: {example_fragments}   [measured]"
    )
    print(
        f"Corner-artifact correlation threshold: {skeleton_result.corner_artifact_corr_threshold}   "
        "[PLACEHOLDER -- see crackgraph/skeleton.py module docstring]"
    )
    example_corner_artifacts = [round(x, 1) for x in skeleton_result.pruned_corner_artifact_lengths[:5]]
    print(
        f"Corner-tracing artifacts pruned: {skeleton_result.n_corner_artifacts_pruned}, "
        f"example lengths: {example_corner_artifacts}   "
        "[interpreted -- medial-axis branches tracing into a concave mask-boundary "
        "corner, flagged by width-vs-position trend, not length]"
    )
    print(f"Prune iterations used: {skeleton_result.iters_used}")
    print()
    print("-- Stage 3: Graph extraction (skan) --")
    n_total_nodes = len(graph_result.node_ids)
    print(
        f"Total nodes: {n_total_nodes}  (endpoints={graph_result.n_endpoints}, "
        f"deg3 junctions={graph_result.n_junctions_deg3}, "
        f"deg>=4 junctions={graph_result.n_junctions_deg_ge4})"
    )
    print(f"Total edges: {graph_result.n_edges}")
    print()
    print("-- Edge curvature & tortuosity (per-edge, independent of junction geometry) --")
    if curvature_result is None:
        print("(skipped, not requested)")
    else:
        print(
            f"Scan window: {curvature_result.window_px:.1f} px    "
            "[PLACEHOLDER -- not calibrated to real h/um-per-px; see scripts/curvature_window_sweep.py]"
        )
        tortuosity_mean, tortuosity_median = tortuosity_stats(curvature_result)
        curvature_mean, curvature_max = curvature_stats(curvature_result)
        n_no_profile = sum(1 for e in curvature_result.edges if e.curvature_profile_px_inv is None)
        if tortuosity_mean is not None:
            print(f"Tortuosity (arc/chord): mean={tortuosity_mean:.3f}, median={tortuosity_median:.3f}    [measured]")
        else:
            print("Tortuosity (arc/chord): no edges with a usable chord length    [measured]")
        if curvature_mean is not None:
            print(f"Curvature |kappa|: mean={curvature_mean:.4f} /px, max={curvature_max:.4f} /px    [measured]")
        else:
            print("Curvature |kappa|: no edges long enough for a windowed profile    [measured]")
        print(
            f"Edges without a curvature profile (shorter than 2x scan window): "
            f"{n_no_profile} of {curvature_result.n_edges_scanned}    [measured]"
        )
    print()
    print("-- Network anisotropy (length-weighted axial orientation tensor) --")
    if anisotropy_result is None:
        print("(skipped, not requested)")
    else:
        print(
            f"Orientation scan window: {anisotropy_result.window_px:.1f} px    "
            "[PLACEHOLDER -- not calibrated to real h/um-per-px]"
        )
        print(
            f"Anisotropy index A: {anisotropy_result.anisotropy_index:.3f} (0=isotropic, 1=perfectly aligned), "
            f"dominant bearing: {anisotropy_result.dominant_bearing_deg:.1f} deg    [measured]"
        )
        if anisotropy_result.anisotropy_index < 0.2:
            print(
                "  (dominant bearing is not meaningful at this low an anisotropy index -- "
                "no clear preferred direction)"
            )
        print(f"Sample count: {anisotropy_result.n_samples}, total weighted length: {anisotropy_result.total_weighted_length_px:.1f} px    [measured]")
        print("Orientation histogram (deg, weighted by arc length)    [measured]:")
        edges_deg = anisotropy_result.histogram_bin_edges_deg
        counts = anisotropy_result.histogram_weighted_counts
        for lo, hi, count in zip(edges_deg[:-1], edges_deg[1:], counts):
            bar = "#" * int(round(count / max(counts.max(), 1e-9) * 40))
            print(f"  [{lo:5.1f}, {hi:5.1f}) {count:8.1f}  {bar}")
        # [PLACEHOLDER -- not calibrated against a real-image junction-type census]
        classification = anisotropy_classification(anisotropy_result)
        print(f"Qualitative read: {classification}    [interpreted]")
        print(
            "  (a low A does not rule out an orthogonal bimodal/grid pattern -- this is a "
            "known blind spot of a 2nd-order orientation tensor; check the histogram above "
            "for two separated peaks before concluding isotropic)"
        )
    print()
    print("-- Edge geometry: length/width/area per atomic edge --")
    print(
        "(width here is physical crack width in px -- METHODOLOGY.md's third chronometer; "
        "NOT the poset antichain width `w` from stage 6, a different quantity)"
    )
    em = edge_metrics_result
    print(
        f"Width trim (inner, per endpoint): {em.width_trim_inner_px:.1f} px    "
        "[PLACEHOLDER -- not calibrated]"
    )
    print(
        f"Area-ambiguity disk radius:       {em.area_ambiguity_radius_px:.1f} px    "
        "[PLACEHOLDER -- same reasoning]"
    )
    print(f"Total length: {em.total_length_px:.1f} px    [measured] (= sum of branch_distance)")
    print("Area estimate bracket (px2), all four methods cross-checked, not collapsed to one number:")
    print(f"  core (junction-disk-excluded): {em.total_area_core_px2}    [interpreted -- PROVEN lower bound]")
    print(f"  exact (watershed partition):   {em.total_area_px2}    [interpreted]")
    print(f"  mask_clean total:              {em.mask_clean_total_px2}    [measured -- PROVEN upper bound]")
    print(
        f"  ribbon-integral (width*ds):    {em.total_area_ribbon_px2:.0f}    "
        f"[interpreted -- EXPECTED, not proven, upper bound; this run: "
        f"{em.n_ribbon_high} edges ran high, {em.n_ribbon_low_or_equal} ran low/equal vs exact]"
    )
    print(
        f"Unassigned (pruned-away, no surviving atom): {em.n_unassigned_px} px2    "
        "[measured -- cross-check against 'Isolated fragments pruned' above]"
    )
    print(
        f"Zero-core edges (too short for a defensible core): {em.n_zero_core_edges}    [interpreted]"
    )
    print(
        f"Width measured for {em.n_width_ok}/{em.n_width_ok + em.n_width_failed} edges "
        f"(excluded length: {em.length_excluded_from_width_stat_px:.1f} px, too short for trim)    "
        "[interpreted]"
    )
    if em.length_weighted_mean_width_px is not None:
        print(f"Length-weighted mean width: {em.length_weighted_mean_width_px:.1f} px    [interpreted]")
    print(
        f"Crack length density: {em.crack_length_density_per_px:.5f} /px    "
        "[interpreted -- px-space only; no um/px calibration exists yet, so only "
        "comparable across images of matching pixel scale]"
    )
    if em.junction_blob_ambiguity:
        print(
            "Junction-blob ambiguity (per degree>=3 node, [interpreted] -- an artifact "
            "of watershed flood order, not a measurement):"
        )
        for jb in em.junction_blob_ambiguity:
            claim_str = ", ".join(
                f"path {p}: {px}px2 ({px / jb.total_blob_px2 * 100:.0f}%)" if jb.total_blob_px2 else f"path {p}: {px}px2"
                for p, px in sorted(jb.claims.items())
            )
            print(
                f"  node {jb.node_id} at ({jb.coord[0]:.1f}, {jb.coord[1]:.1f}): "
                f"radius={jb.radius_px:.1f}px, blob={jb.total_blob_px2}px2 -- {claim_str}"
            )
    print("Per-edge table (see also " + str(edge_metrics_csv_path) + "):")
    for path_index in sorted(em.per_edge):
        m = em.per_edge[path_index]
        w = m.width
        width_str = f"width_mean={w.mean_px:.1f}px (n={w.n_samples})" if w.ok else f"width=n/a ({w.failure_reason})"
        print(
            f"  path {path_index}: length={m.length_px:.1f}px {width_str} "
            f"area=[core={m.area_core_px2} exact={m.area_px2} ribbon={m.area_ribbon_px2:.0f}]px2 "
            f"(ambiguous={m.area_ambiguous_px2}px2, {m.area_ambiguous_frac * 100:.0f}%)"
        )
    print()
    print("-- Stage 4: Junction classification (annulus tangent-fit method) --")
    if junction_result is None:
        print("(skipped, not requested)")
    else:
        print(
            f"Annulus radii: inner={junction_result.inner_radius_px:.1f} px, "
            f"outer={junction_result.outer_radius_px:.1f} px    "
            "[PLACEHOLDER -- not calibrated to real h/um-per-px]"
        )
        print(
            f"Classification tolerances: Y +/-{junction_result.y_angle_tol_deg:.1f} deg, "
            f"T-straight +/-{junction_result.t_straight_tol_deg:.1f} deg, "
            f"T-right-angle +/-{junction_result.t_right_tol_deg:.1f} deg    [PLACEHOLDER]"
        )
        print(f"Degree-3 junctions: {junction_result.n_deg3_total}")
        print(f"  T: {junction_result.n_t}    [interpreted]")
        print(f"  Y: {junction_result.n_y}    [interpreted]")
        print(f"  ambiguous: {junction_result.n_ambiguous}    [interpreted]")
        print(
            f"  insufficient annulus data: {junction_result.n_insufficient_data}    "
            "[interpreted -- geometry could not be measured; see failure_reason]"
        )
        print(
            f"Degree>=4 junctions (report-only, not classified): "
            f"{junction_result.n_deg_ge4_unclassified}    [measured]"
        )
        print(
            "(sector gaps: the 3 angular gaps between arm bearings, sorted, sum to 360 "
            "exactly -- signed bearings, not unsigned pairwise angles, so reflex gaps "
            "show correctly instead of being folded into [0,180])"
        )
        for c in junction_result.classifications:
            row, col = c.coord
            if c.label == "insufficient_data":
                print(f"  node {c.node_id} at ({row:.1f}, {col:.1f}): insufficient_data ({c.failure_reason})")
            else:
                gaps = ", ".join(f"{g:.1f}" for g in c.sector_gaps_deg)
                gap_sum = sum(c.sector_gaps_deg)
                extra = ""
                if c.label == "T":
                    by_path = {ed.path_index: ed for ed in c.edge_directions}
                    host_curvs = ", ".join(
                        f"{by_path[p].curvature_per_px:+.4f}" if by_path[p].curvature_per_px is not None else "n/a"
                        for p in c.host_path_indices
                    )
                    extra = (
                        f"  abutter=path{c.abutter_path_index} host=paths{c.host_path_indices}"
                        f" host_curv=[{host_curvs}]/px"
                    )
                print(
                    f"  node {c.node_id} at ({row:.1f}, {col:.1f}): {c.label}  "
                    f"gaps=[{gaps}] (sum={gap_sum:.1f}){extra}"
                )
    print()
    print("-- Corner cross-check (background-tile walls, independent of the annulus fit) --")
    if corner_check_skipped:
        reason = "not requested" if args.skip_corner_cross_check else "requires junction classification"
        print(f"(skipped, {reason})")
    else:
        print(
            f"Search radius: {args.corner_search_radius_px:.1f} px, window: {args.corner_window_px:.1f} px, "
            f"min turn: {args.corner_min_turn_deg:.1f} deg    [PLACEHOLDER -- see corners.py]"
        )
        n_agree, n_disagree, n_unresolved = corner_agreement_counts(corner_cross_check)
        print(
            f"Agree: {n_agree}, disagree: {n_disagree}, unresolved: {n_unresolved} "
            f"(of {len(corner_cross_check)})    [interpreted -- a validation signal per METHODOLOGY.md's "
            "independent-chronometer philosophy, not a tiebreaker]"
        )
        for cc in corner_cross_check:
            if cc.label is None:
                print(f"  node {cc.node_id}: unresolved ({cc.unresolved_reason}, {len(cc.corners)} corners found)")
            else:
                # agrees_with_tangent_fit is None when the tangent-fit had no
                # comparable gaps to check against (e.g. insufficient_data) --
                # that's "not comparable", not a disagreement, so keep it a
                # distinct flag rather than folding it into [DISAGREE].
                if cc.agrees_with_tangent_fit is False:
                    flag = "  [DISAGREE]"
                elif cc.agrees_with_tangent_fit is None:
                    flag = "  [N/A: tangent-fit not comparable]"
                else:
                    flag = ""
                gaps = ", ".join(f"{g:.1f}" for g in cc.sector_gaps_deg)
                max_diff = (
                    f"{cc.max_gap_disagreement_deg:.1f}" if cc.max_gap_disagreement_deg is not None else "n/a"
                )
                print(
                    f"  node {cc.node_id}: {cc.label} gaps=[{gaps}] "
                    f"(max diff vs tangent-fit: {max_diff} deg){flag}"
                )
    print()
    print("-- Stage 5: Precedence graph (first pass -- graph + cycle report, not yet resolved) --")
    if precedence_result is None:
        reason = "not requested" if args.skip_precedence else "requires junction classification"
        print(f"(skipped, {reason})")
    else:
        n_by_both = sum(a.methods_agree for a in precedence_result.arcs)
        n_by_tangent = sum(a.supporting_methods == ("tangent_fit",) for a in precedence_result.arcs)
        n_by_corner = sum(a.supporting_methods == ("corner_cross_check",) for a in precedence_result.arcs)
        print(
            f"Arcs: {len(precedence_result.arcs)} total "
            f"(both methods agree: {n_by_both}, tangent-fit only: {n_by_tangent}, "
            f"corner-cross-check only: {n_by_corner})    [interpreted -- union of both stage-4 classifiers]"
        )
        print(
            f"Conflicting abutter (both methods resolved T, disagreed on which arm): "
            f"{precedence_result.n_conflicting_abutter}    [interpreted -- no arc emitted, not guessed]"
        )
        if precedence_result.conflicting_node_ids:
            print(f"  nodes: {precedence_result.conflicting_node_ids}")
        print(
            f"Corner-resolved T not mapped to path indices: {precedence_result.n_corner_unmapped}    "
            "[interpreted -- see precedence.py module docstring]"
        )
        n_touched = precedence_result.graph.number_of_nodes()
        n_determined = sum(g is not None for g in precedence_result.generation.values())
        print(
            f"Atomic edges touched by >=1 precedence arc: {n_touched} of {graph_result.n_edges} total    "
            "[measured]"
        )
        print(
            f"  of those, with a determined generation: {n_determined}    "
            f"[interpreted -- {n_touched - n_determined} undetermined because caught in an unresolved cycle]"
        )
        print(
            f"Nontrivial cycles (strongly-connected clusters, size > 1): "
            f"{len(precedence_result.nontrivial_sccs)}    "
            "[measured -- reported per METHODOLOGY.md, NOT deleted or force-resolved this pass]"
        )
        for scc in precedence_result.nontrivial_sccs:
            print(f"  cluster of {len(scc)} atomic edges: paths {sorted(scc)}")
    print()
    print("-- Output --")
    dim_note = "" if scale >= 1.0 else f" (downsampled by {scale:.3f}x)"
    print(f"Overlay saved to: {out_path}{dim_note}")
    if detail_out_path is not None:
        print(f"Detail overlay saved to: {detail_out_path}")
    if precedence_out_path is not None:
        print(f"Precedence graph overlay saved to: {precedence_out_path}")
    else:
        print("Precedence graph overlay: not generated (skipped)")
    print(f"Edge geometry (length/width/area, all four area methods) CSV saved to: {edge_metrics_csv_path}")

    if args.xlsx_out is not None:
        append_chunk_to_workbook(
            args.xlsx_out,
            image_path=image_path,
            region_desc=region_desc,
            region=region if not args.full_image else None,
            full_image_shape=(full_h, full_w),
            binarize_result=binarize_result,
            skeleton_result=skeleton_result,
            graph_result=graph_result,
            curvature_result=curvature_result,
            anisotropy_result=anisotropy_result,
            junction_result=junction_result,
            corner_cross_check=corner_cross_check,
            overlay_png_path=out_path,
            out_dir=out_dir,
        )
        print(f"Appended chunk to workbook: {args.xlsx_out} (sheet={image_path.stem!r})")


if __name__ == "__main__":
    main()
