"""CLI entry point: analyse one image in detail.

Binarize, skeletonize, flaking exclusion, graph, then per-edge curvature,
tortuosity, network anisotropy and per-edge length/width/area.

Usage:
    python3 -m src.analyze_image <image_path> [options]

Analyses a top-left corner crop of the image (see crackgraph/region.py)
unless --full-image is passed.
"""

import argparse
import dataclasses
from pathlib import Path

import numpy as np
import skan
import skimage

from .crackgraph.anisotropy import ORIENT_WINDOW_PX_PLACEHOLDER, compute_anisotropy
from .crackgraph.binarize import binarize
from .crackgraph.curvature import CURVATURE_WINDOW_PX_PLACEHOLDER, compute_edge_curvature
from .crackgraph.edge_metrics import (
    AREA_JUNCTION_BLOB_RADIUS_PLACEHOLDER,
    WIDTH_TRIM_INNER_PX_PLACEHOLDER,
    compute_edge_metrics,
    write_edge_metrics_csv,
)
from .crackgraph.flaking import exclude_flaking_regions, remove_flake_touching_edges
from .crackgraph.graph import extract_graph
from .crackgraph.io_utils import load_image
from .crackgraph.overlay import render_overlay
from .crackgraph.region import default_corner_crop
from .crackgraph.skeleton import SPUR_PX_PLACEHOLDER, skeletonize_and_prune
from .crackgraph.xlsx_report import (
    ANISOTROPY_MUDCRACK_LIKE_THRESHOLD,
    anisotropy_classification,
    append_chunk_to_workbook,
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
    p = argparse.ArgumentParser(description="Detailed crack-network analysis of a single image.")
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
    p.add_argument("--no-host-stub-pruning", action="store_true",
                   help="Keep dead ends with less than spur_px of their length outside their host crack.")
    p.add_argument("--min-object-px", type=int, default=4)
    p.add_argument("--max-overlay-dim", type=int, default=2500)
    p.add_argument("--corner-frac", type=float, default=0.125)
    p.add_argument("--edge-margin-frac", type=float, default=0.02)
    p.add_argument("--curvature-window-px", type=float, default=CURVATURE_WINDOW_PX_PLACEHOLDER)
    p.add_argument("--orientation-window-px", type=float, default=ORIENT_WINDOW_PX_PLACEHOLDER)
    p.add_argument("--width-trim-inner-px", type=float, default=WIDTH_TRIM_INNER_PX_PLACEHOLDER)
    p.add_argument("--area-ambiguity-radius-px", type=float, default=AREA_JUNCTION_BLOB_RADIUS_PLACEHOLDER)
    p.add_argument(
        "--full-image",
        action="store_true",
        default=False,
        help="Process the whole image instead of the default corner crop.",
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
    args = p.parse_args()
    skip_flags_set = args.skip_curvature or args.skip_anisotropy
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
        # The area share travels with every result that quotes region_desc (console
        # report, xlsx row, GUI), so numbers from this crop can't be mistaken
        # for whole-image numbers like the batch crack stats.
        area_pct = 100.0 * crop_h * crop_w / (full_h * full_w)
        region_desc = (
            f"top-left corner, {crop_w} x {crop_h} px, {area_pct:.1f}% of image area "
            f"[corner-frac={region.corner_frac}, edge-margin-frac={region.edge_margin_frac}]"
        )
        stem_suffix = "corner"

    binarize_result = binarize(gray)

    # Single pass: skeletonize once, find flaked regions from that skeleton's
    # width map, then remove every edge touching a flaked region from the
    # skeleton and rebuild the graph, so no analysis below runs through a
    # region we have no evidence about. See crackgraph/flaking.py.
    skeleton_result = skeletonize_and_prune(
        binarize_result.mask,
        source_image=gray,
        min_object_px=args.min_object_px,
        spur_px=args.spur_px,
        prune_host_stubs=not args.no_host_stub_pruning,
    )
    flaking_result = exclude_flaking_regions(
        skeleton_result.mask_clean,
        skeleton_result.skel_image,
        skeleton_result.medial_radius,
    )
    kept_skeleton, graph_result, flake_omitted = remove_flake_touching_edges(
        skeleton_result.skeleton, extract_graph(skeleton_result.skeleton), flaking_result.excluded_mask,
    )
    if flake_omitted:
        # Downstream stages read the skeleton and the crack mask from
        # skeleton_result: give them the flake-free versions. medial_radius
        # stays the width map of the whole cleaned mask, as in the batch export.
        skeleton_result = dataclasses.replace(
            skeleton_result,
            skeleton=kept_skeleton,
            skel_image=kept_skeleton.skeleton_image,
            mask_clean=flaking_result.mask_corrected,
        )
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
    # Nest under the image's own source folder (e.g. data/raw/T5,
    # data/raw/humidity_loading) so outputs from different coatings/sample
    # batches don't pile up flat in one directory.
    out_dir = Path(args.out_dir) / image_path.parent.name
    out_dir.mkdir(parents=True, exist_ok=True)
    edge_metrics_csv_path = out_dir / f"{image_path.stem}_{stem_suffix}_edge_metrics.csv"
    write_edge_metrics_csv(edge_metrics_result, edge_metrics_csv_path)
    out_path = out_dir / f"{image_path.stem}_{stem_suffix}_overlay.png"
    scale = render_overlay(
        rgb,
        skeleton_result.skeleton,
        graph_result,
        out_path,
        max_overlay_dim=args.max_overlay_dim,
    )
    print(f"=== Crack-network report: {image_path.name} ===")
    print(f"Image (full):     {full_w} x {full_h} px, RGB")
    print(f"Region analyzed:  {region_desc}")
    if not args.full_image:
        print("                  (pass --full-image to analyse the whole image)")
    print()
    print("-- Parameters (every value used, for reproducing this exact report) --")
    for name, value in vars(args).items():
        print(f"  --{name.replace('_', '-')} = {value}")
    print(f"  library versions: numpy={np.__version__}, skimage={skimage.__version__}, skan={skan.__version__}")
    print()
    print("-- Stage 1: Binarize --")
    print(f"Threshold value:        {binarize_result.threshold:.2f}        [measured]")
    print(f"Foreground fraction:    {binarize_result.foreground_fraction * 100:.2f}%     [measured]")
    print()
    print("-- Flaking/delamination exclusion (see crackgraph/flaking.py) --")
    print(
        f"Reference crack width (this image, skeleton-median): "
        f"{flaking_result.reference_width_px:.1f} px    [measured]"
    )
    print(
        f"Candidates found: {len(flaking_result.candidates)}    "
        "[interpreted -- flagged by local width only, not junction-blob-filtered yet]"
    )
    for c in flaking_result.candidates:
        print(f"  area={c.area_px} px  solidity={c.solidity:.3f}  bbox={c.bbox}")
    print(
        f"Excluded area: {flaking_result.excluded_area_px} px "
        f"({flaking_result.excluded_area_pct:.3f}% of image)    [measured]"
    )
    if flaking_result.candidates:
        print(
            f"Skeleton edges touching a flaked region, removed before graph analysis: "
            f"{len(flake_omitted)}    [measured] -- excluded pixels are not counted as crack area."
        )
    print()
    print("-- Stage 2: Skeletonize + prune --")
    print(
        f"Skeleton pixel count (pre/post-prune): "
        f"{skeleton_result.n_pixels_pre_prune}/{skeleton_result.n_pixels_post_prune}   [measured]"
    )
    print(
        f"Spur length threshold:   {skeleton_result.spur_px_threshold} px    "
        "[derived -- 15 px = 9.1 um on mm images, see docs/calibration_notes.md]"
    )
    example_spurs = [round(x, 1) for x in skeleton_result.pruned_spur_lengths[:5]]
    print(f"Spurs pruned: {skeleton_result.n_spurs_pruned}, example lengths: {example_spurs}   [measured]")
    example_fragments = [round(x, 1) for x in skeleton_result.pruned_fragment_lengths[:5]]
    print(
        f"Isolated fragments pruned: {skeleton_result.n_fragments_pruned}, "
        f"example lengths: {example_fragments}   [measured]"
    )
    example_host_stubs = [round(x, 1) for x in skeleton_result.pruned_host_stub_lengths[:5]]
    print(
        f"Host stubs pruned: {skeleton_result.n_host_stubs_pruned} "
        f"(rule {'on' if skeleton_result.prune_host_stubs else 'off'}), "
        f"example lengths: {example_host_stubs}   "
        "[interpreted -- dead ends with less than spur_px of their length outside "
        "the crack they branch from]"
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
            "[PLACEHOLDER -- not calibrated to real h/um-per-px; see scripts/validation/curvature_window_sweep.py]"
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
        if anisotropy_result.anisotropy_index < ANISOTROPY_MUDCRACK_LIKE_THRESHOLD:
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
        # [PLACEHOLDER -- not calibrated against real images]
        classification = anisotropy_classification(anisotropy_result)
        print(f"Qualitative read: {classification}    [interpreted]")
        print(
            "  (a low A does not rule out an orthogonal bimodal/grid pattern -- this is a "
            "known blind spot of a 2nd-order orientation tensor; check the histogram above "
            "for two separated peaks before concluding isotropic)"
        )
    print()
    print("-- Edge geometry: length/width/area per atomic edge --")
    em = edge_metrics_result
    print(
        f"Width trim (inner, per endpoint): {em.width_trim_inner_px:.1f} px    "
        "[PLACEHOLDER -- not calibrated]"
    )
    print(
        f"Area-ambiguity disk radius:       {em.area_ambiguity_radius_px:.1f} px    "
        "[PLACEHOLDER -- same reasoning]"
    )
    print(
        f"Total length: {em.total_length_px:.1f} px    [measured] (= sum of branch_distance, "
        "edges touching a flaked region already removed)"
    )
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
    print("-- Output --")
    dim_note = "" if scale >= 1.0 else f" (downsampled by {scale:.3f}x)"
    print(f"Overlay saved to: {out_path}{dim_note}")
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
            overlay_png_path=out_path,
            out_dir=out_dir,
        )
        print(f"Appended chunk to workbook: {args.xlsx_out} (sheet={image_path.stem!r})")


if __name__ == "__main__":
    main()
