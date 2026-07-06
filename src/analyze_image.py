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
from .crackgraph.kinks import (
    KINK_TURN_DEG_PLACEHOLDER,
    KINK_WINDOW_PX_PLACEHOLDER,
    find_kinks,
)
from .crackgraph.overlay import render_overlay
from .crackgraph.region import default_corner_crop
from .crackgraph.skeleton import SPUR_PX_PLACEHOLDER, skeletonize_and_prune
from .crackgraph.xlsx_report import (
    anisotropy_classification,
    append_chunk_to_workbook,
    corner_agreement_counts,
    curvature_stats,
    tortuosity_stats,
)


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
    p.add_argument("--kink-window-px", type=float, default=KINK_WINDOW_PX_PLACEHOLDER)
    p.add_argument("--kink-turn-deg", type=float, default=KINK_TURN_DEG_PLACEHOLDER)
    p.add_argument("--corner-search-radius-px", type=float, default=CORNER_SEARCH_RADIUS_PX)
    p.add_argument("--corner-window-px", type=float, default=CORNER_WINDOW_PX)
    p.add_argument("--corner-min-turn-deg", type=float, default=CORNER_MIN_TURN_DEG)
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
    return p.parse_args()


def main():
    args = parse_args()
    image_path = Path(args.image_path)
    gray_full, rgb_full = load_image(image_path)
    full_h, full_w = gray_full.shape

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
    skeleton_result = skeletonize_and_prune(
        binarize_result.mask,
        source_image=gray,
        min_object_px=args.min_object_px,
        spur_px=args.spur_px,
    )
    graph_result = extract_graph(skeleton_result.skeleton)
    curvature_result = compute_edge_curvature(
        skeleton_result.skeleton,
        graph_result,
        window_px=args.curvature_window_px,
    )
    anisotropy_result = compute_anisotropy(
        skeleton_result.skeleton,
        graph_result,
        window_px=args.orientation_window_px,
    )
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
    kink_result = find_kinks(
        skeleton_result.skeleton,
        graph_result,
        window_px=args.kink_window_px,
        min_turn_deg=args.kink_turn_deg,
    )
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

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{image_path.stem}_{stem_suffix}_overlay.png"
    scale = render_overlay(
        rgb,
        skeleton_result.skeleton,
        graph_result,
        out_path,
        max_overlay_dim=args.max_overlay_dim,
        junction_result=junction_result,
        kink_result=kink_result,
        corner_cross_check=corner_cross_check,
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
            kink_result=kink_result,
            corner_cross_check=corner_cross_check,
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
    print("-- Stage 4: Junction classification (annulus tangent-fit method) --")
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
    print("-- Edge kink scan (flag-only, no splitting) --")
    print(
        f"Kink window: {kink_result.window_px:.1f} px, min turn: {kink_result.min_turn_deg:.1f} deg"
        "    [PLACEHOLDER -- not calibrated]"
    )
    print(
        f"Kinks flagged: {len(kink_result.kinks)} across {kink_result.n_edges_scanned} edges    "
        "[interpreted -- suspected two distinct cracks fused into one edge; "
        "topology NOT changed, splitting deferred]"
    )
    for k in kink_result.kinks:
        print(
            f"  path {k.path_index} at ({k.coord[0]:.1f}, {k.coord[1]:.1f}): "
            f"turn={k.turn_angle_deg:.1f} deg   [measured]"
        )
    print()
    print("-- Corner cross-check (background-tile walls, independent of the annulus fit) --")
    print(
        f"Search radius: {args.corner_search_radius_px:.1f} px, window: {args.corner_window_px:.1f} px, "
        f"min turn: {args.corner_min_turn_deg:.1f} deg    [PLACEHOLDER -- see corners.py]"
    )
    n_agree, n_disagree, n_unresolved = corner_agreement_counts(corner_cross_check)
    print(
        f"Agree: {n_agree}, disagree: {n_disagree}, unresolved: {n_unresolved} "
        f"(of {len(corner_cross_check)})    [interpreted -- a validation signal per CLAUDE.md's "
        "independent-chronometer philosophy, not a tiebreaker]"
    )
    for cc in corner_cross_check:
        if cc.label is None:
            print(f"  node {cc.node_id}: unresolved ({cc.unresolved_reason}, {len(cc.corners)} corners found)")
        else:
            flag = "" if cc.agrees_with_tangent_fit else "  [DISAGREE]"
            gaps = ", ".join(f"{g:.1f}" for g in cc.sector_gaps_deg)
            print(
                f"  node {cc.node_id}: {cc.label} gaps=[{gaps}] "
                f"(max diff vs tangent-fit: {cc.max_gap_disagreement_deg:.1f} deg){flag}"
            )
    print()
    print("-- Output --")
    dim_note = "" if scale >= 1.0 else f" (downsampled by {scale:.3f}x)"
    print(f"Overlay saved to: {out_path}{dim_note}")
    if detail_out_path is not None:
        print(f"Detail overlay saved to: {detail_out_path}")

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
            kink_result=kink_result,
            corner_cross_check=corner_cross_check,
            overlay_png_path=out_path,
            out_dir=out_dir,
        )
        print(f"Appended chunk to workbook: {args.xlsx_out} (sheet={image_path.stem!r})")


if __name__ == "__main__":
    main()
