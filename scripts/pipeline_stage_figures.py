"""Pipeline-stage walkthrough figures for crack_stats_v3.

Two modes:

- **Full** (default): 8 panels -- raw crop, binarized mask, mask cleaning
  (small objects removed / small holes filled, highlighted), the pre-prune
  (raw) skeleton, the pruned branches (spur/fragment/corner-artifact, shown
  as one undifferentiated "pruned" category) called out in color, the
  cleaned (post-prune) skeleton, the delaminated region shaded in (when
  present), and the final graph with excluded edges *and* nodes marked.
- **Compact** (`--compact`): 4 panels for external hand-off -- raw crop,
  mask cleaning + skeletonize + prune consolidated into one panel, flake
  identification, and the final graph.

Reuses scripts/export_crack_stats_v3.py's exact stage functions (binarize,
skeletonize_and_prune, exclude_flaking_regions, extract_graph,
flake_touching_path_indices) in the same order compute_row() calls them --
this script only adds a render step after each stage instead of proceeding
straight to stats.

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
    python3 -m scripts.pipeline_stage_figures <image_path> [--out-dir outputs/crack_stats_v3/pipeline_walkthrough] [--compact]
"""

import argparse
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from scipy.ndimage import binary_dilation
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

# Display-only skeleton dilation -- doesn't affect any real measurement,
# exists purely so a thin, sparse 1px skeleton line doesn't get visually
# lost once matplotlib downsamples a multi-thousand-pixel crop for a 7x7in
# figure. (Background is left at full black/white contrast -- no dimming.)
SKELETON_DILATE_PX = 2

SKELETON_COLOR = "lime"
OMITTED_EDGE_COLOR = "magenta"
FLAKING_TINT_COLOR = (1.0, 0.0, 0.0, 0.3)
KEPT_NODE_COLOR = "cyan"
EXCLUDED_NODE_COLOR = "gold"

# Single undifferentiated "pruned" color -- spur/fragment/corner-artifact are
# deliberately not distinguished here (that would need a 3-color legend for a
# distinction most viewers of this figure don't need); chosen to not collide
# with the palette above, per this project's own "don't reuse hues across
# unrelated categorical layers" lesson.
PRUNED_COLOR = "orange"

# Mask-cleaning diff color (small objects removed + small holes filled by
# remove_small_objects/remove_small_holes) -- a blue, distinct from every
# other color in this figure set (lime/magenta/red-tint/cyan/gold/orange).
MASK_CLEAN_DIFF_COLOR = "dodgerblue"

STAGE_FILENAMES = {
    "raw": "01_raw_crop.png",
    "binarized": "02_binarized.png",
    "mask_cleaned": "03_mask_cleaned.png",
    "skeleton_raw": "04_skeleton_raw.png",
    "pruning": "05_pruning_annotated.png",
    "skeleton_cleaned": "06_skeleton_cleaned.png",
    "flaking": "07_flaking_shaded.png",
    "graph": "08_graph_final.png",
}

COMPACT_STAGE_FILENAMES = {
    "raw": "01_raw_crop.png",
    "clean_skeleton_pruned": "02_clean_skeletonize_prune.png",
    "flaking": "03_flaking.png",
    "graph": "04_graph_final.png",
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


def draw_raw(ax, rgb_crop, title="1. Raw image"):
    ax.imshow(rgb_crop)
    ax.set_title(title, fontsize=11)
    ax.axis("off")


def draw_binarized(ax, mask_crop):
    ax.imshow(mask_crop, cmap="gray", vmin=0, vmax=1)
    ax.set_title("2. Binarized mask (Otsu)", fontsize=11)
    ax.axis("off")


def draw_skeleton(ax, mask_crop, skel_crop, title):
    # Dilate the skeleton for display only -- makes a thin, sparse skeleton
    # line legible after matplotlib downsamples the crop; see
    # SKELETON_DILATE_PX above. Doesn't change any real data. Background
    # stays plain black/white, full contrast.
    ax.imshow(mask_crop, cmap="gray", vmin=0, vmax=1)
    skel_display = binary_dilation(skel_crop, iterations=SKELETON_DILATE_PX)
    skel_rgba = np.zeros((*skel_display.shape, 4))
    skel_rgba[skel_display] = matplotlib.colors.to_rgba(SKELETON_COLOR)
    ax.imshow(skel_rgba)
    ax.set_title(title, fontsize=11)
    ax.axis("off")


def draw_mask_cleaned(ax, mask_clean_crop, diff_crop):
    """The cleaned mask (post remove_small_objects/remove_small_holes), with
    every pixel that changed from the raw Otsu mask -- a small object
    removed, or a small hole filled -- highlighted in one color. Spur/hole
    sub-types are deliberately not distinguished, same simplification as
    draw_pruning_annotated below."""
    ax.imshow(mask_clean_crop, cmap="gray", vmin=0, vmax=1)
    diff_rgba = np.zeros((*diff_crop.shape, 4))
    diff_rgba[diff_crop] = matplotlib.colors.to_rgba(MASK_CLEAN_DIFF_COLOR)
    ax.imshow(diff_rgba)
    ax.plot([], [], color=MASK_CLEAN_DIFF_COLOR, linewidth=6, label="speck removed/filled")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.03), ncol=1, fontsize=8, framealpha=0.9)
    ax.set_title("3. Mask cleaning (small objects removed / small holes filled)", fontsize=11)
    ax.axis("off")


def draw_clean_skeleton_pruned(ax, mask_clean_crop, mask_clean_diff_crop, skel_final_crop, pruned_branches, bbox, title):
    """Compact-mode panel consolidating mask cleaning + skeletonize + prune
    into one view: cleaned mask as background (specks highlighted), the
    final kept skeleton in skeleton color, and every pruned branch in the
    pruned color -- kept + pruned together reconstruct the pre-prune
    skeleton implicitly, without a separate raw-skeleton panel."""
    y0, y1, x0, x1 = bbox
    ax.imshow(mask_clean_crop, cmap="gray", vmin=0, vmax=1)

    diff_rgba = np.zeros((*mask_clean_diff_crop.shape, 4))
    diff_rgba[mask_clean_diff_crop] = matplotlib.colors.to_rgba(MASK_CLEAN_DIFF_COLOR)
    ax.imshow(diff_rgba)

    skel_display = binary_dilation(skel_final_crop, iterations=SKELETON_DILATE_PX)
    skel_rgba = np.zeros((*skel_display.shape, 4))
    skel_rgba[skel_display] = matplotlib.colors.to_rgba(SKELETON_COLOR)
    ax.imshow(skel_rgba)

    segments = []
    for rec in pruned_branches:
        local = rec.coords - [y0, x0]
        seg = local[:, ::-1]  # (row, col) -> (x, y)
        segments.append(seg)
    if segments:
        ax.add_collection(LineCollection(segments, colors=PRUNED_COLOR, linewidths=1.8, zorder=3))

    ax.plot([], [], color=MASK_CLEAN_DIFF_COLOR, linewidth=6, label="speck removed/filled")
    ax.plot([], [], color=SKELETON_COLOR, linewidth=2.5, label="kept skeleton")
    ax.plot([], [], color=PRUNED_COLOR, linewidth=1.8, label="pruned")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.03), ncol=3, fontsize=8, framealpha=0.9)

    ax.set_xlim(0, x1 - x0)
    ax.set_ylim(y1 - y0, 0)
    ax.set_title(title, fontsize=11)
    ax.axis("off")


def draw_flaking_shaded(ax, mask_crop, skel_crop, excluded_crop, title):
    draw_skeleton(ax, mask_crop, skel_crop, title)
    excl_rgba = np.zeros((*excluded_crop.shape, 4))
    excl_rgba[excluded_crop] = FLAKING_TINT_COLOR
    ax.imshow(excl_rgba)


def draw_pruning_annotated(ax, mask_crop, skel_raw_crop, pruned_branches, bbox):
    """Pre-prune skeleton with every pruned branch (spur, fragment, or
    corner-artifact -- not distinguished from one another) drawn in one
    color. Branches not pruned remain plain skeleton-colored, same as
    draw_skeleton's other panels."""
    y0, y1, x0, x1 = bbox
    draw_skeleton(ax, mask_crop, skel_raw_crop, "5. Pruned branches (spur / fragment / corner-artifact)")

    segments = []
    for rec in pruned_branches:
        local = rec.coords - [y0, x0]
        seg = local[:, ::-1]  # (row, col) -> (x, y)
        segments.append(seg)

    if segments:
        ax.add_collection(LineCollection(segments, colors=PRUNED_COLOR, linewidths=1.8, zorder=3))

    ax.plot([], [], color=PRUNED_COLOR, linewidth=1.8, label="pruned")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.03), ncol=1, fontsize=8, framealpha=0.9)

    ax.set_xlim(0, x1 - x0)
    ax.set_ylim(y1 - y0, 0)


def draw_graph_excluded(ax, mask_crop, excluded_crop, skel, graph_result, omitted, bbox, title):
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
    ax.set_title(title, fontsize=11)
    ax.axis("off")


def _save_combined(panels, out_dir, image_path, crop_mode, n_rows, n_cols):
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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("image_path", type=str)
    p.add_argument("--out-dir", type=str, default="outputs/crack_stats_v3/pipeline_walkthrough")
    p.add_argument("--compact", action="store_true",
                    help="4-panel mode (raw / clean+skeletonize+prune / flaking / final graph) "
                         "for external hand-off, instead of the full 8-panel breakdown")
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
    crop_mode = "flaking"
    if bbox is None:
        bbox = compute_corner_crop_bbox(gray.shape)
        crop_mode = "corner-default"
    y0, y1, x0, x1 = bbox
    print(f"{image_path.name}: crop_mode={crop_mode}, rows {y0}:{y1}, cols {x0}:{x1} "
          f"({y1-y0}x{x1-x0}px, reference_width_px={flaking_result.reference_width_px:.2f})")

    rgb_crop = rgb[y0:y1, x0:x1]
    mask_crop = binarize_result.mask[y0:y1, x0:x1]
    mask_clean_crop = skeleton_result.mask_clean[y0:y1, x0:x1]
    mask_clean_diff_crop = mask_crop != mask_clean_crop
    skel_clean_crop = skeleton_result.skel_image[y0:y1, x0:x1]
    excluded_crop = flaking_result.excluded_mask[y0:y1, x0:x1]
    has_flaking_in_crop = bool(excluded_crop.any())

    out_dir = Path(args.out_dir) / image_path.stem
    # Wipe and recreate rather than mkdir(exist_ok=True) -- a re-run after any
    # renumbering/renaming of stage files must never leave stale files behind
    # from a previous run sitting alongside the current ones.
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True)

    panels = []  # (key, draw_fn) for the combined figure, in order
    readme_lines = [f"# {image_path.stem} -- pipeline stage walkthrough", "",
                     f"Crop: {crop_mode} mode, rows {y0}:{y1}, cols {x0}:{x1} ({y1-y0}x{x1-x0}px).",
                     "", "| File | Stage |", "|---|---|"]

    if args.compact:
        fn = COMPACT_STAGE_FILENAMES

        fig, ax = plt.subplots(figsize=(7, 7))
        draw_raw(ax, rgb_crop)
        fig.savefig(out_dir / fn["raw"], dpi=150, bbox_inches="tight")
        plt.close(fig)
        panels.append(("raw", lambda ax: draw_raw(ax, rgb_crop)))
        readme_lines.append(f"| `{fn['raw']}` | Raw image, cropped |")

        fig, ax = plt.subplots(figsize=(7, 7))
        draw_clean_skeleton_pruned(ax, mask_clean_crop, mask_clean_diff_crop, skel_clean_crop,
                                    skeleton_result.pruned_branches, bbox,
                                    "2. Mask cleaning + skeletonize + prune")
        fig.savefig(out_dir / fn["clean_skeleton_pruned"], dpi=150, bbox_inches="tight")
        plt.close(fig)
        panels.append(("clean_skeleton_pruned", lambda ax: draw_clean_skeleton_pruned(
            ax, mask_clean_crop, mask_clean_diff_crop, skel_clean_crop,
            skeleton_result.pruned_branches, bbox, "2. Mask cleaning + skeletonize + prune")))
        readme_lines.append(f"| `{fn['clean_skeleton_pruned']}` | Mask cleaning (specks) + skeletonize + prune, consolidated |")

        if has_flaking_in_crop:
            fig, ax = plt.subplots(figsize=(7, 7))
            draw_flaking_shaded(ax, mask_crop, skel_clean_crop, excluded_crop, "3. Flake identification")
            fig.savefig(out_dir / fn["flaking"], dpi=150, bbox_inches="tight")
            plt.close(fig)
            panels.append(("flaking", lambda ax: draw_flaking_shaded(ax, mask_crop, skel_clean_crop, excluded_crop, "3. Flake identification")))
            readme_lines.append(f"| `{fn['flaking']}` | Skeleton with the delaminated/flaking region shaded |")
        else:
            print(f"{image_path.name}: no flaking within the chosen crop -- skipping {fn['flaking']}")

        fig, ax = plt.subplots(figsize=(7, 7))
        draw_graph_excluded(ax, mask_crop, excluded_crop, skeleton_result.skeleton, graph_result, omitted, bbox,
                             "4. Final graph -- excluded edges & nodes marked")
        fig.savefig(out_dir / fn["graph"], dpi=150, bbox_inches="tight")
        plt.close(fig)
        panels.append(("graph", lambda ax: draw_graph_excluded(
            ax, mask_crop, excluded_crop, skeleton_result.skeleton, graph_result, omitted, bbox,
            "4. Final graph -- excluded edges & nodes marked")))
        readme_lines.append(f"| `{fn['graph']}` | Final graph: kept/omitted edges and nodes |")

        _save_combined(panels, out_dir, image_path, crop_mode, n_rows=2, n_cols=2)

    else:
        fn = STAGE_FILENAMES
        skel_raw_image = skimage_skeletonize(skeleton_result.mask_clean)  # display-only, pre-prune
        skel_raw_crop = skel_raw_image[y0:y1, x0:x1]

        fig, ax = plt.subplots(figsize=(7, 7))
        draw_raw(ax, rgb_crop)
        fig.savefig(out_dir / fn["raw"], dpi=150, bbox_inches="tight")
        plt.close(fig)
        panels.append(("raw", lambda ax: draw_raw(ax, rgb_crop)))
        readme_lines.append(f"| `{fn['raw']}` | Raw image, cropped |")

        fig, ax = plt.subplots(figsize=(7, 7))
        draw_binarized(ax, mask_crop)
        fig.savefig(out_dir / fn["binarized"], dpi=150, bbox_inches="tight")
        plt.close(fig)
        panels.append(("binarized", lambda ax: draw_binarized(ax, mask_crop)))
        readme_lines.append(f"| `{fn['binarized']}` | Binarized mask (Otsu) |")

        fig, ax = plt.subplots(figsize=(7, 7))
        draw_mask_cleaned(ax, mask_clean_crop, mask_clean_diff_crop)
        fig.savefig(out_dir / fn["mask_cleaned"], dpi=150, bbox_inches="tight")
        plt.close(fig)
        panels.append(("mask_cleaned", lambda ax: draw_mask_cleaned(ax, mask_clean_crop, mask_clean_diff_crop)))
        readme_lines.append(f"| `{fn['mask_cleaned']}` | Cleaned mask, with small objects removed / small holes filled highlighted |")

        fig, ax = plt.subplots(figsize=(7, 7))
        draw_skeleton(ax, mask_crop, skel_raw_crop, "4. Raw skeleton (pre-prune, single pass)")
        fig.savefig(out_dir / fn["skeleton_raw"], dpi=150, bbox_inches="tight")
        plt.close(fig)
        panels.append(("skeleton_raw", lambda ax: draw_skeleton(ax, mask_crop, skel_raw_crop, "4. Raw skeleton (pre-prune, single pass)")))
        readme_lines.append(f"| `{fn['skeleton_raw']}` | Raw skeleton, pre-prune (single thinning pass) |")

        fig, ax = plt.subplots(figsize=(7, 7))
        draw_pruning_annotated(ax, mask_crop, skel_raw_crop, skeleton_result.pruned_branches, bbox)
        fig.savefig(out_dir / fn["pruning"], dpi=150, bbox_inches="tight")
        plt.close(fig)
        panels.append(("pruning", lambda ax: draw_pruning_annotated(ax, mask_crop, skel_raw_crop, skeleton_result.pruned_branches, bbox)))
        readme_lines.append(f"| `{fn['pruning']}` | Pruned branches (spur / fragment / corner-artifact, not distinguished) |")

        fig, ax = plt.subplots(figsize=(7, 7))
        draw_skeleton(ax, mask_crop, skel_clean_crop, "6. Cleaned skeleton (post-prune)")
        fig.savefig(out_dir / fn["skeleton_cleaned"], dpi=150, bbox_inches="tight")
        plt.close(fig)
        panels.append(("skeleton_cleaned", lambda ax: draw_skeleton(ax, mask_crop, skel_clean_crop, "6. Cleaned skeleton (post-prune)")))
        readme_lines.append(f"| `{fn['skeleton_cleaned']}` | Cleaned skeleton, post-prune |")

        if has_flaking_in_crop:
            fig, ax = plt.subplots(figsize=(7, 7))
            draw_flaking_shaded(ax, mask_crop, skel_clean_crop, excluded_crop, "7. Skeleton + delaminated region shaded")
            fig.savefig(out_dir / fn["flaking"], dpi=150, bbox_inches="tight")
            plt.close(fig)
            panels.append(("flaking", lambda ax: draw_flaking_shaded(ax, mask_crop, skel_clean_crop, excluded_crop, "7. Skeleton + delaminated region shaded")))
            readme_lines.append(f"| `{fn['flaking']}` | Skeleton with the delaminated/flaking region shaded |")
        else:
            print(f"{image_path.name}: no flaking within the chosen crop -- skipping {fn['flaking']}")

        fig, ax = plt.subplots(figsize=(7, 7))
        draw_graph_excluded(ax, mask_crop, excluded_crop, skeleton_result.skeleton, graph_result, omitted, bbox,
                             "8. Final graph -- excluded edges & nodes marked")
        fig.savefig(out_dir / fn["graph"], dpi=150, bbox_inches="tight")
        plt.close(fig)
        panels.append(("graph", lambda ax: draw_graph_excluded(
            ax, mask_crop, excluded_crop, skeleton_result.skeleton, graph_result, omitted, bbox,
            "8. Final graph -- excluded edges & nodes marked")))
        readme_lines.append(f"| `{fn['graph']}` | Final graph: kept/omitted edges and nodes |")

        _save_combined(panels, out_dir, image_path, crop_mode, n_rows=2, n_cols=4)

    readme_lines.append("| `combined.png` | All panels above, side by side |")
    (out_dir / "README.md").write_text("\n".join(readme_lines) + "\n")

    print(f"Wrote {len(panels) + 1} figures + README to {out_dir}")


if __name__ == "__main__":
    main()
