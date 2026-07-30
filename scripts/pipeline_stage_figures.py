"""Pipeline-stage walkthrough figures for crack_stats_v3: renders the
binarized mask, the initial (single-pass) skeleton overlaid on it, that same
skeleton with the delaminated region shaded in, and the final graph with
excluded edges *and* nodes marked -- all cropped to the largest flaking
region in the image, for visually verifying the pipeline and producing
reusable figures.

Reuses scripts/export_crack_stats_v3.py's exact stage functions (binarize,
skeletonize_and_prune, exclude_flaking_regions, extract_graph,
flake_touching_path_indices) in the same order compute_row() calls them --
this script only adds a render step after each stage instead of proceeding
straight to stats.

Node kept/excluded status (not drawn by src/crackgraph/overlay.py's
render_crack_stats_overlay, which only colors edges) is computed the same
way compute_row()'s own connectivity graph G is: a node is "kept" if it has
at least one non-omitted edge, "excluded" otherwise.

Usage:
    python3 -m scripts.pipeline_stage_figures <image_path> [--out-dir outputs/crack_stats_v3/pipeline_walkthrough]
"""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from skimage.measure import label, regionprops

from src.crackgraph.binarize import binarize
from src.crackgraph.flaking import exclude_flaking_regions, flake_touching_path_indices
from src.crackgraph.graph import extract_graph
from src.crackgraph.io_utils import load_image
from src.crackgraph.skeleton import skeletonize_and_prune

# Padding around the largest flaking candidate's bbox, in multiples of the
# image's own reference crack width -- ties crop context to crack scale
# rather than a fixed pixel constant (matches flaking.py's own
# GROWTH_MULTIPLIER precedent). Floor of 400px so a very fine-cracked image
# (small reference_width_px) still gets a legible amount of surrounding
# network, not just the bare candidate blob.
CROP_PADDING_WIDTH_MULTIPLIER = 25.0
CROP_PADDING_FLOOR_PX = 400

SKELETON_COLOR = "lime"
OMITTED_EDGE_COLOR = "magenta"
FLAKING_TINT_COLOR = (1.0, 0.0, 0.0, 0.3)
KEPT_NODE_COLOR = "cyan"
EXCLUDED_NODE_COLOR = "gold"


def compute_crop_bbox(excluded_mask, reference_width_px, image_shape):
    """(y0, y1, x0, x1) around the largest-area flaking candidate, padded and
    clamped to image bounds. None if there are no candidates at all."""
    labeled = label(excluded_mask)
    regions = regionprops(labeled)
    if not regions:
        return None
    largest = max(regions, key=lambda r: r.area)
    y0, x0, y1, x1 = largest.bbox
    pad = max(CROP_PADDING_FLOOR_PX, int(CROP_PADDING_WIDTH_MULTIPLIER * reference_width_px))
    h, w = image_shape
    return max(0, y0 - pad), min(h, y1 + pad), max(0, x0 - pad), min(w, x1 + pad)


def draw_binarized(ax, mask_crop):
    ax.imshow(mask_crop, cmap="gray", vmin=0, vmax=1)
    ax.set_title("1. Binarized mask (Otsu)", fontsize=11)
    ax.axis("off")


def draw_skeleton(ax, mask_crop, skel_crop, title):
    ax.imshow(mask_crop, cmap="gray", vmin=0, vmax=1)
    skel_rgba = np.zeros((*skel_crop.shape, 4))
    skel_rgba[skel_crop] = matplotlib.colors.to_rgba(SKELETON_COLOR)
    ax.imshow(skel_rgba)
    ax.set_title(title, fontsize=11)
    ax.axis("off")


def draw_flaking_shaded(ax, mask_crop, skel_crop, excluded_crop):
    draw_skeleton(ax, mask_crop, skel_crop, "3. Skeleton + delaminated region shaded")
    excl_rgba = np.zeros((*excluded_crop.shape, 4))
    excl_rgba[excluded_crop] = FLAKING_TINT_COLOR
    ax.imshow(excl_rgba)


def draw_graph_excluded(ax, mask_crop, excluded_crop, skel, graph_result, omitted, bbox):
    y0, y1, x0, x1 = bbox
    summary = graph_result.summary

    ax.imshow(mask_crop, cmap="gray", vmin=0, vmax=1)
    excl_rgba = np.zeros((*excluded_crop.shape, 4))
    excl_rgba[excluded_crop] = FLAKING_TINT_COLOR
    ax.imshow(excl_rgba)

    kept_segments, omitted_segments = [], []
    for path_index in summary.index:
        coords = skel.path_coordinates(int(path_index))
        local = coords - [y0, x0]
        seg = local[:, ::-1]  # (row, col) -> (x, y)
        (omitted_segments if int(path_index) in omitted else kept_segments).append(seg)
    if kept_segments:
        ax.add_collection(LineCollection(kept_segments, colors=SKELETON_COLOR, linewidths=1.0, zorder=2))
    if omitted_segments:
        ax.add_collection(LineCollection(omitted_segments, colors=OMITTED_EDGE_COLOR, linewidths=1.6, zorder=3))

    # Node kept/excluded status: kept iff it has >=1 non-omitted edge, i.e.
    # it survives into compute_row()'s own connectivity graph G -- computed
    # the same way, not a separate/different criterion.
    kept_summary = summary.loc[~summary.index.isin(omitted)]
    kept_node_ids = set(kept_summary["node_id_src"]).union(kept_summary["node_id_dst"])

    node_coords = graph_result.node_coords  # (row, col)
    node_ids = graph_result.node_ids
    in_crop = (
        (node_coords[:, 0] >= y0) & (node_coords[:, 0] < y1)
        & (node_coords[:, 1] >= x0) & (node_coords[:, 1] < x1)
    )
    coords_local = node_coords[in_crop] - [y0, x0]
    is_kept = np.array([int(nid) in kept_node_ids for nid in node_ids[in_crop]])

    if is_kept.any():
        pts = coords_local[is_kept]
        ax.scatter(pts[:, 1], pts[:, 0], s=20, c=KEPT_NODE_COLOR, edgecolors="black",
                   linewidths=0.4, zorder=4)
    if (~is_kept).any():
        pts = coords_local[~is_kept]
        ax.scatter(pts[:, 1], pts[:, 0], s=26, c=EXCLUDED_NODE_COLOR, edgecolors="black",
                   linewidths=0.4, zorder=5)

    ax.plot([], [], color=SKELETON_COLOR, linewidth=1.6, label="kept edge")
    ax.plot([], [], color=OMITTED_EDGE_COLOR, linewidth=1.6, label="omitted edge")
    ax.scatter([], [], c=KEPT_NODE_COLOR, edgecolors="black", linewidths=0.4, s=20, label="kept node")
    ax.scatter([], [], c=EXCLUDED_NODE_COLOR, edgecolors="black", linewidths=0.4, s=26, label="excluded node")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.03), ncol=4, fontsize=7.5, framealpha=0.9)

    ax.set_xlim(0, x1 - x0)
    ax.set_ylim(y1 - y0, 0)
    ax.set_title("4. Final graph -- excluded edges & nodes marked", fontsize=11)
    ax.axis("off")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("image_path", type=str)
    p.add_argument("--out-dir", type=str, default="outputs/crack_stats_v3/pipeline_walkthrough")
    args = p.parse_args()

    image_path = Path(args.image_path)
    gray, rgb = load_image(image_path)

    binarize_result = binarize(gray)
    skeleton_result = skeletonize_and_prune(binarize_result.mask, source_image=gray)
    flaking_result = exclude_flaking_regions(
        skeleton_result.mask_clean, skeleton_result.skel_image, skeleton_result.medial_radius,
    )
    graph_result = extract_graph(skeleton_result.skeleton)
    omitted = flake_touching_path_indices(
        skeleton_result.skeleton, graph_result, flaking_result.excluded_mask,
    )

    bbox = compute_crop_bbox(flaking_result.excluded_mask, flaking_result.reference_width_px, gray.shape)
    if bbox is None:
        raise SystemExit(f"{image_path.name}: no flaking candidates found -- nothing to crop around")
    y0, y1, x0, x1 = bbox
    print(f"{image_path.name}: cropping to rows {y0}:{y1}, cols {x0}:{x1} "
          f"({y1-y0}x{x1-x0}px, reference_width_px={flaking_result.reference_width_px:.2f})")

    mask_crop = binarize_result.mask[y0:y1, x0:x1]
    skel_crop = skeleton_result.skel_image[y0:y1, x0:x1]
    excluded_crop = flaking_result.excluded_mask[y0:y1, x0:x1]

    out_dir = Path(args.out_dir) / image_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(7, 7))
    draw_binarized(ax, mask_crop)
    fig.savefig(out_dir / "01_binarized.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 7))
    draw_skeleton(ax, mask_crop, skel_crop, "2. Initial skeleton (single pass)")
    fig.savefig(out_dir / "02_skeleton.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 7))
    draw_flaking_shaded(ax, mask_crop, skel_crop, excluded_crop)
    fig.savefig(out_dir / "03_flaking_shaded.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 7))
    draw_graph_excluded(ax, mask_crop, excluded_crop, skeleton_result.skeleton, graph_result, omitted, bbox)
    fig.savefig(out_dir / "04_graph_excluded.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(13, 13))
    draw_binarized(axes[0, 0], mask_crop)
    draw_skeleton(axes[0, 1], mask_crop, skel_crop, "2. Initial skeleton (single pass)")
    draw_flaking_shaded(axes[1, 0], mask_crop, skel_crop, excluded_crop)
    draw_graph_excluded(axes[1, 1], mask_crop, excluded_crop, skeleton_result.skeleton, graph_result, omitted, bbox)
    fig.suptitle(f"{image_path.stem} -- pipeline stage walkthrough", fontsize=14)
    fig.tight_layout()
    fig.savefig(out_dir / "combined.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    print(f"Wrote 5 figures to {out_dir}")


if __name__ == "__main__":
    main()
