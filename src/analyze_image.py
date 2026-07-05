"""CLI entry point: run stage 1-3 on a single image.

Usage:
    python3 -m src.analyze_image <image_path> [options]

For now this always analyzes only a top-left corner crop of the image
(see crackgraph/region.py) unless --full-image is passed -- full-image
runs are deferred until this corner check is validated (see README).
"""

import argparse
from pathlib import Path

from .crackgraph.binarize import binarize
from .crackgraph.graph import extract_graph
from .crackgraph.io_utils import load_image
from .crackgraph.overlay import render_overlay
from .crackgraph.region import default_corner_crop
from .crackgraph.skeleton import SPUR_PX_PLACEHOLDER, skeletonize_and_prune


def parse_args():
    p = argparse.ArgumentParser(description="Stage 1-3 crack-graph pipeline (single image).")
    p.add_argument("image_path", type=str)
    p.add_argument("--out-dir", type=str, default="outputs")
    p.add_argument("--spur-px", type=float, default=SPUR_PX_PLACEHOLDER)
    p.add_argument("--min-object-px", type=int, default=4)
    p.add_argument("--max-overlay-dim", type=int, default=2500)
    p.add_argument("--otsu-sanity-band", type=float, nargs=2, default=(0.01, 0.15))
    p.add_argument("--corner-frac", type=float, default=0.125)
    p.add_argument("--edge-margin-frac", type=float, default=0.02)
    p.add_argument(
        "--full-image",
        action="store_true",
        default=False,
        help="Process the whole image instead of the default corner crop (not used yet, see README).",
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

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{image_path.stem}_{stem_suffix}_overlay.png"
    scale = render_overlay(
        rgb,
        skeleton_result.skeleton,
        graph_result,
        out_path,
        max_overlay_dim=args.max_overlay_dim,
    )

    print(f"=== Stage 1-3 report: {image_path.name} ===")
    print(f"Image (full):     {full_w} x {full_h} px, RGB")
    print(f"Region analyzed:  {region_desc}")
    if not args.full_image:
        print("                  (full-image run skipped for now -- pass --full-image to override)")
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
    print("Note: T-vs-Y classification and angle measurement are out of scope here.")
    print()
    print("-- Output --")
    dim_note = "" if scale >= 1.0 else f" (downsampled by {scale:.3f}x)"
    print(f"Overlay saved to: {out_path}{dim_note}")


if __name__ == "__main__":
    main()
