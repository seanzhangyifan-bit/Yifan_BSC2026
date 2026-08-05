"""Shared pipeline-stage panel-drawing functions.

Extracted from scripts/pipeline_stage_figures.py (the real-image walkthrough
script) so both that script and scripts/synthetic_benchmark_report.py render
raw/binarized/skeleton/graph panels with the same code instead of duplicating
it. Only the panels genuinely shared between a real-image walkthrough and a
synthetic-case report live here -- the real-image script's flaking-specific
panels (mask cleaning, consolidated clean+skeletonize+prune, flake shading,
pruning-annotated) stay in that script, since none of this project's 9
synthetic-benchmark cases involve flaking.
"""

import matplotlib
import numpy as np
from matplotlib.collections import LineCollection
from scipy.ndimage import binary_dilation

# Display-only skeleton dilation -- doesn't affect any real measurement,
# exists purely so a thin, sparse 1px skeleton line doesn't get visually
# lost once matplotlib downsamples a crop for a figure.
SKELETON_DILATE_PX = 2

SKELETON_COLOR = "lime"
OMITTED_EDGE_COLOR = "magenta"
FLAKING_TINT_COLOR = (1.0, 0.0, 0.0, 0.3)
KEPT_NODE_COLOR = "cyan"
EXCLUDED_NODE_COLOR = "gold"


def draw_raw(ax, rgb_crop, title="1. Raw image"):
    ax.imshow(rgb_crop)
    ax.set_title(title, fontsize=11)
    ax.axis("off")


def draw_binarized(ax, mask_crop, title="2. Binarized mask (Otsu)"):
    ax.imshow(mask_crop, cmap="gray", vmin=0, vmax=1)
    ax.set_title(title, fontsize=11)
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


def draw_graph_excluded(ax, mask_crop, excluded_crop, skel, graph_result, omitted, bbox, title):
    """Final graph, kept edges/nodes vs. omitted (flaking-adjacent) ones in
    a different color. Callers with no flaking concept at all (every
    synthetic-benchmark case) pass an all-False excluded_crop and an empty
    omitted set -- every edge/node then renders as "kept", the flaking tint
    layer draws nothing, and this reduces to a plain final-graph panel
    without needing a separate no-flaking code path.
    """
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
