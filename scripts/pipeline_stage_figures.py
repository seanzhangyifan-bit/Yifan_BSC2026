"""Pipeline-stage walkthrough figures for crack_stats_v3: renders the raw
crop, the binarized mask, the pre-prune (raw) skeleton, the pruned branches
(spur/fragment/corner-artifact) called out in color, the cleaned (post-prune)
skeleton, the delaminated region shaded in (when present), and the final
graph with excluded edges *and* nodes marked -- for visually verifying the
pipeline and producing reusable figures.

Reuses scripts/export_crack_stats_v3.py's exact stage functions (binarize,
skeletonize_and_prune, exclude_flaking_regions, extract_graph,
flake_touching_path_indices) in the same order compute_row() calls them --
this script only adds a render step after each stage instead of proceeding
straight to stats. The one extra computation not part of compute_row() is a
second, display-only call to skimage.morphology.skeletonize() on the same
mask_clean skeletonize_and_prune already used, to recover the pre-prune
skeleton for the pruning-annotated panel -- cheap (one pass, no pruning loop)
and does not affect any real pipeline output.

Crop selection: anchors on the largest flaking candidate the same way as
before when the image has any (flaking_result.excluded_mask non-empty);
otherwise falls back to src/crackgraph/region.py's default_corner_crop --
the project's own established "first look" region -- so this script runs on
any image regardless of whether it has flaking, not just flaking-heavy ones.

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
from skimage.morphology import skeletonize as skimage_skeletonize

from src.crackgraph.binarize import binarize
from src.crackgraph.flaking import exclude_flaking_regions, flake_touching_path_indices
from src.crackgraph.graph import extract_graph
from src.crackgraph.io_utils import load_image
from src.crackgraph.region import default_corner_crop
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

# Pruning-reason colors -- chosen to not collide with the palette above
# (lime/magenta/red-tint/cyan/gold already in use in this same figure set),
# per this project's own "don't reuse hues across unrelated categorical
# layers" lesson.
SPUR_COLOR = "deepskyblue"
FRAGMENT_COLOR = "darkorange"
CORNER_ARTIFACT_COLOR = "yellow"
PRUNE_COLOR_BY_REASON = {
    "spur": SPUR_COLOR,
    "fragment": FRAGMENT_COLOR,
    "corner_artifact": CORNER_ARTIFACT_COLOR,
}

STAGE_FILENAMES = {
    "raw": "01_raw_crop.png",
    "binarized": "02_binarized.png",
    "skeleton_raw": "03_skeleton_raw.png",
    "pruning": "04_pruning_annotated.png",
    "skeleton_cleaned": "05_skeleton_cleaned.png",
    "flaking": "06_flaking_shaded.png",
    "graph": "07_graph_final.png",
}


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


def compute_corner_crop_bbox(image_shape):
    """(y0, y1, x0, x1) for the project's established default top-left
    corner crop (src/crackgraph/region.py) -- used as the fallback whenever
    an image has no flaking candidate to anchor a crop on."""
    h, w = image_shape
    region = default_corner_crop(h, w)
    return region.row_slice.start, region.row_slice.stop, region.col_slice.start, region.col_slice.stop


def draw_raw(ax, rgb_crop):
    ax.imshow(rgb_crop)
    ax.set_title("1. Raw image", fontsize=11)
    ax.axis("off")


def draw_binarized(ax, mask_crop):
    ax.imshow(mask_crop, cmap="gray", vmin=0, vmax=1)
    ax.set_title("2. Binarized mask (Otsu)", fontsize=11)
    ax.axis("off")


def draw_skeleton(ax, mask_crop, skel_crop, title):
    ax.imshow(mask_crop, cmap="gray", vmin=0, vmax=1)
    skel_rgba = np.zeros((*skel_crop.shape, 4))
    skel_rgba[skel_crop] = matplotlib.colors.to_rgba(SKELETON_COLOR)
    ax.imshow(skel_rgba)
    ax.set_title(title, fontsize=11)
    ax.axis("off")


def draw_flaking_shaded(ax, mask_crop, skel_crop, excluded_crop):
    draw_skeleton(ax, mask_crop, skel_crop, "6. Skeleton + delaminated region shaded")
    excl_rgba = np.zeros((*excluded_crop.shape, 4))
    excl_rgba[excluded_crop] = FLAKING_TINT_COLOR
    ax.imshow(excl_rgba)


def draw_pruning_annotated(ax, mask_crop, skel_raw_crop, pruned_branches, bbox):
    """Pre-prune skeleton with every pruned branch drawn in a color keyed to
    why it was removed -- spur (short dead end), fragment (short isolated
    piece), or corner_artifact (medial-axis branch tracing into a concave
    mask corner, per skeleton.py's correlation test). Branches not pruned
    remain plain skeleton-colored, same as draw_skeleton's other panels."""
    y0, y1, x0, x1 = bbox
    draw_skeleton(ax, mask_crop, skel_raw_crop, "4. Pruned branches (spur / fragment / corner-artifact)")

    segments_by_reason = {"spur": [], "fragment": [], "corner_artifact": []}
    for rec in pruned_branches:
        local = rec.coords - [y0, x0]
        seg = local[:, ::-1]  # (row, col) -> (x, y)
        segments_by_reason[rec.reason].append(seg)

    for reason, segs in segments_by_reason.items():
        if segs:
            ax.add_collection(LineCollection(segs, colors=PRUNE_COLOR_BY_REASON[reason], linewidths=1.8, zorder=3))

    for reason, color in PRUNE_COLOR_BY_REASON.items():
        ax.plot([], [], color=color, linewidth=1.8, label=reason.replace("_", " "))
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.03), ncol=3, fontsize=8, framealpha=0.9)

    ax.set_xlim(0, x1 - x0)
    ax.set_ylim(y1 - y0, 0)


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
    ax.set_title("7. Final graph -- excluded edges & nodes marked", fontsize=11)
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
    skel_raw_image = skimage_skeletonize(skeleton_result.mask_clean)  # display-only, pre-prune
    flaking_result = exclude_flaking_regions(
        skeleton_result.mask_clean, skeleton_result.skel_image, skeleton_result.medial_radius,
    )
    graph_result = extract_graph(skeleton_result.skeleton)
    omitted = flake_touching_path_indices(
        skeleton_result.skeleton, graph_result, flaking_result.excluded_mask,
    )

    bbox = compute_crop_bbox(flaking_result.excluded_mask, flaking_result.reference_width_px, gray.shape)
    crop_mode = "flaking"
    if bbox is None:
        bbox = compute_corner_crop_bbox(gray.shape)
        crop_mode = "corner-default"
    y0, y1, x0, x1 = bbox
    print(f"{image_path.name}: crop_mode={crop_mode}, rows {y0}:{y1}, cols {x0}:{x1} "
          f"({y1-y0}x{x1-x0}px, reference_width_px={flaking_result.reference_width_px:.2f})")

    rgb_crop = rgb[y0:y1, x0:x1]
    mask_crop = binarize_result.mask[y0:y1, x0:x1]
    skel_raw_crop = skel_raw_image[y0:y1, x0:x1]
    skel_clean_crop = skeleton_result.skel_image[y0:y1, x0:x1]
    excluded_crop = flaking_result.excluded_mask[y0:y1, x0:x1]
    has_flaking_in_crop = bool(excluded_crop.any())

    out_dir = Path(args.out_dir) / image_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    panels = []  # (key, draw_fn) for the combined figure, in order

    fig, ax = plt.subplots(figsize=(7, 7))
    draw_raw(ax, rgb_crop)
    fig.savefig(out_dir / STAGE_FILENAMES["raw"], dpi=150, bbox_inches="tight")
    plt.close(fig)
    panels.append(("raw", lambda ax: draw_raw(ax, rgb_crop)))

    fig, ax = plt.subplots(figsize=(7, 7))
    draw_binarized(ax, mask_crop)
    fig.savefig(out_dir / STAGE_FILENAMES["binarized"], dpi=150, bbox_inches="tight")
    plt.close(fig)
    panels.append(("binarized", lambda ax: draw_binarized(ax, mask_crop)))

    fig, ax = plt.subplots(figsize=(7, 7))
    draw_skeleton(ax, mask_crop, skel_raw_crop, "3. Raw skeleton (pre-prune, single pass)")
    fig.savefig(out_dir / STAGE_FILENAMES["skeleton_raw"], dpi=150, bbox_inches="tight")
    plt.close(fig)
    panels.append(("skeleton_raw", lambda ax: draw_skeleton(ax, mask_crop, skel_raw_crop, "3. Raw skeleton (pre-prune, single pass)")))

    fig, ax = plt.subplots(figsize=(7, 7))
    draw_pruning_annotated(ax, mask_crop, skel_raw_crop, skeleton_result.pruned_branches, bbox)
    fig.savefig(out_dir / STAGE_FILENAMES["pruning"], dpi=150, bbox_inches="tight")
    plt.close(fig)
    panels.append(("pruning", lambda ax: draw_pruning_annotated(ax, mask_crop, skel_raw_crop, skeleton_result.pruned_branches, bbox)))

    fig, ax = plt.subplots(figsize=(7, 7))
    draw_skeleton(ax, mask_crop, skel_clean_crop, "5. Cleaned skeleton (post-prune)")
    fig.savefig(out_dir / STAGE_FILENAMES["skeleton_cleaned"], dpi=150, bbox_inches="tight")
    plt.close(fig)
    panels.append(("skeleton_cleaned", lambda ax: draw_skeleton(ax, mask_crop, skel_clean_crop, "5. Cleaned skeleton (post-prune)")))

    if has_flaking_in_crop:
        fig, ax = plt.subplots(figsize=(7, 7))
        draw_flaking_shaded(ax, mask_crop, skel_clean_crop, excluded_crop)
        fig.savefig(out_dir / STAGE_FILENAMES["flaking"], dpi=150, bbox_inches="tight")
        plt.close(fig)
        panels.append(("flaking", lambda ax: draw_flaking_shaded(ax, mask_crop, skel_clean_crop, excluded_crop)))
    else:
        print(f"{image_path.name}: no flaking within the chosen crop -- skipping {STAGE_FILENAMES['flaking']}")

    fig, ax = plt.subplots(figsize=(7, 7))
    draw_graph_excluded(ax, mask_crop, excluded_crop, skeleton_result.skeleton, graph_result, omitted, bbox)
    fig.savefig(out_dir / STAGE_FILENAMES["graph"], dpi=150, bbox_inches="tight")
    plt.close(fig)
    panels.append(("graph", lambda ax: draw_graph_excluded(ax, mask_crop, excluded_crop, skeleton_result.skeleton, graph_result, omitted, bbox)))

    n_cols = 4
    n_rows = 2
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(6.5 * n_cols, 6.5 * n_rows))
    flat_axes = axes.flat
    for (_, draw_fn), ax in zip(panels, flat_axes):
        draw_fn(ax)
    for ax in list(flat_axes)[len(panels):]:
        ax.axis("off")
    fig.suptitle(f"{image_path.stem} -- pipeline stage walkthrough (crop_mode={crop_mode})", fontsize=14)
    fig.tight_layout()
    fig.savefig(out_dir / "combined.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    readme_lines = [
        f"# {image_path.stem} -- pipeline stage walkthrough",
        "",
        f"Crop: {crop_mode} mode, rows {y0}:{y1}, cols {x0}:{x1} ({y1-y0}x{x1-x0}px).",
        "",
        "| File | Stage |",
        "|---|---|",
        f"| `{STAGE_FILENAMES['raw']}` | Raw image, cropped |",
        f"| `{STAGE_FILENAMES['binarized']}` | Binarized mask (Otsu) |",
        f"| `{STAGE_FILENAMES['skeleton_raw']}` | Raw skeleton, pre-prune (single thinning pass) |",
        f"| `{STAGE_FILENAMES['pruning']}` | Pruned branches called out by reason (spur / fragment / corner-artifact) |",
        f"| `{STAGE_FILENAMES['skeleton_cleaned']}` | Cleaned skeleton, post-prune |",
    ]
    if has_flaking_in_crop:
        readme_lines.append(f"| `{STAGE_FILENAMES['flaking']}` | Skeleton with the delaminated/flaking region shaded |")
    readme_lines.append(f"| `{STAGE_FILENAMES['graph']}` | Final graph: kept/omitted edges and nodes |")
    readme_lines.append("| `combined.png` | All panels above, side by side |")
    (out_dir / "README.md").write_text("\n".join(readme_lines) + "\n")

    print(f"Wrote {len(panels) + 1} figures + README to {out_dir}")


if __name__ == "__main__":
    main()
