"""Overlay rendering: skeleton + endpoint/junction markers on the original image.

Analysis always runs at the full resolution of the region being processed.
Only this saved visualization is downsampled, and only the *image
background* is resampled (LANCZOS) -- skeleton/node coordinates are scaled
numerically instead of resampling the (often 1px-wide) skeleton bitmap,
which would blur or break under any resampling filter.

The legend is drawn *below* the axes (bbox_to_anchor with a negative y),
not on top of the image -- an earlier version placed it inside the axes at
the top right and it regularly covered real junctions.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import skan
from matplotlib.collections import LineCollection
from PIL import Image

from .graph import GraphResult


def render_overlay(
    rgb: np.ndarray,
    skel: skan.Skeleton,
    graph_result: GraphResult,
    out_path: str | Path,
    *,
    max_overlay_dim: int = 2500,
) -> float:
    """Save an overlay PNG: the skeleton, endpoints (degree 1) and junctions
    (degree >= 3). Returns the scale factor used for the display image."""
    h, w = rgb.shape[:2]
    scale = min(1.0, max_overlay_dim / max(h, w))

    if scale < 1.0:
        new_size = (round(w * scale), round(h * scale))
        display_rgb = np.asarray(Image.fromarray(rgb).resize(new_size, Image.LANCZOS))
    else:
        display_rgb = rgb

    disp_h, disp_w = display_rgb.shape[:2]
    dpi = 150
    fig, ax = plt.subplots(figsize=(disp_w / dpi, disp_h / dpi), dpi=dpi)
    ax.imshow(display_rgb)

    n_edges = len(graph_result.summary)
    if n_edges > 0:
        segments = []
        for path_index in graph_result.summary.index:
            coords = skel.path_coordinates(int(path_index)) * scale  # (row, col)
            segments.append(coords[:, ::-1])  # -> (col, row) == (x, y)
        lc = LineCollection(segments, colors="lime", linewidths=0.6, zorder=2)
        ax.add_collection(lc)

    degree = graph_result.node_degree
    coords = graph_result.node_coords * scale  # (row, col)
    endpoints = coords[degree == 1]
    junctions = coords[degree >= 3]
    if len(endpoints) > 0:
        ax.scatter(
            endpoints[:, 1], endpoints[:, 0], s=6, c="orange", zorder=3,
            label="endpoint (deg 1)",
        )
    if len(junctions) > 0:
        ax.scatter(
            junctions[:, 1], junctions[:, 0], s=10, c="red", zorder=4,
            label="junction (deg>=3)",
        )

    ax.set_xlim(0, disp_w)
    ax.set_ylim(disp_h, 0)
    ax.axis("off")
    if len(endpoints) > 0 or len(junctions) > 0:
        # Below the axes, not on top of the image -- see module docstring.
        ax.legend(
            loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=3,
            fontsize=6, markerscale=1.3, framealpha=0.9,
        )

    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return scale


def _spreadsheet_col_label(n: int) -> str:
    """0-indexed column number -> spreadsheet-style label (0->A, 25->Z,
    26->AA, ...)."""
    label = ""
    n += 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        label = chr(65 + rem) + label
    return label


def render_crack_stats_overlay(
    rgb: np.ndarray,
    skel: skan.Skeleton,
    graph_result: GraphResult,
    excluded_mask: np.ndarray,
    omitted_path_indices: set[int],
    out_path: str | Path,
    *,
    max_overlay_dim: int = 2500,
    grid_cell_px: int | None = None,
) -> float:
    """Save a crack-stats-scoped overlay PNG: the final pruned skeleton,
    the flaking-exclusion region tinted, and edges touching it (from
    flaking.flake_touching_path_indices, omitted from the stats and the
    connectivity graph) highlighted -- the corrections the crack-stats
    numbers already reflect, made visible. Scoped to stage 1-3, like
    the export itself (see docs/batch_stats/crack_stats_schema.md). Same downsampling
    convention as render_overlay: only the background is resampled
    (LANCZOS for the photo, NEAREST for the boolean mask so its edges stay
    sharp rather than blurring into fractional alpha), skeleton/edge
    coordinates are scaled numerically. Returns the scale factor used.

    grid_cell_px (default None, e.g. pass 700 to enable): spreadsheet-style
    labeled grid squares (row letters A/B/C.. down the left, column
    numbers 1/2/3.. across the top, e.g. "square E4") instead of raw pixel
    coordinates -- meant to be pointed at verbally ("the speck is in E4"),
    not read as a precise coordinate. Cell boundaries are still defined in
    ORIGINAL full-resolution pixel coordinates internally, so a square can
    always be translated back to an exact pixel range if needed.
    """
    h, w = rgb.shape[:2]
    scale = min(1.0, max_overlay_dim / max(h, w))

    if scale < 1.0:
        new_size = (round(w * scale), round(h * scale))
        display_rgb = np.asarray(Image.fromarray(rgb).resize(new_size, Image.LANCZOS))
        display_excluded = np.asarray(
            Image.fromarray(excluded_mask).resize(new_size, Image.NEAREST)
        )
    else:
        display_rgb = rgb
        display_excluded = excluded_mask

    disp_h, disp_w = display_rgb.shape[:2]
    dpi = 150
    fig, ax = plt.subplots(figsize=(disp_w / dpi, disp_h / dpi), dpi=dpi)
    ax.imshow(display_rgb)

    if display_excluded.any():
        excl_overlay = np.zeros((disp_h, disp_w, 4))
        excl_overlay[display_excluded] = [1.0, 0.0, 0.0, 0.3]
        ax.imshow(excl_overlay, zorder=1)

    n_edges = len(graph_result.summary)
    if n_edges > 0:
        kept_segments = []
        cut_segments = []
        for path_index in graph_result.summary.index:
            coords = skel.path_coordinates(int(path_index)) * scale  # (row, col)
            seg = coords[:, ::-1]  # -> (col, row) == (x, y)
            if int(path_index) in omitted_path_indices:
                cut_segments.append(seg)
            else:
                kept_segments.append(seg)

        if kept_segments:
            ax.add_collection(LineCollection(kept_segments, colors="lime", linewidths=0.6, zorder=2))
        if cut_segments:
            ax.plot([], [], color="magenta", linewidth=1.4,
                     label="touches flaking region (omitted from stats and connectivity)")
            ax.add_collection(
                LineCollection(cut_segments, colors="magenta", linewidths=1.4, zorder=3)
            )

    if display_excluded.any():
        ax.plot([], [], color="red", linewidth=6, alpha=0.3, label="flaking-excluded region")

    ax.set_xlim(0, disp_w)
    ax.set_ylim(disp_h, 0)
    ax.axis("off")

    if grid_cell_px is not None:
        x_bounds = np.arange(0, w, grid_cell_px)
        if x_bounds[-1] < w:
            x_bounds = np.append(x_bounds, w)
        y_bounds = np.arange(0, h, grid_cell_px)
        if y_bounds[-1] < h:
            y_bounds = np.append(y_bounds, h)

        for x in x_bounds:
            ax.axvline(x * scale, color="cyan", linewidth=0.4, alpha=0.5, zorder=9)
        for y in y_bounds:
            ax.axhline(y * scale, color="cyan", linewidth=0.4, alpha=0.5, zorder=9)

        label_style = dict(
            fontsize=7, color="cyan", zorder=10, ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.1", fc="black", ec="cyan", lw=0.5, alpha=0.75),
        )
        n_cols = len(x_bounds) - 1
        n_rows = len(y_bounds) - 1
        for c in range(n_cols):
            mid_x = (x_bounds[c] + x_bounds[c + 1]) / 2 * scale
            ax.annotate(str(c + 1), xy=(mid_x, 10), xycoords="data", **label_style)
        for r in range(n_rows):
            mid_y = (y_bounds[r] + y_bounds[r + 1]) / 2 * scale
            ax.annotate(_spreadsheet_col_label(r), xy=(10, mid_y), xycoords="data", **label_style)

    if display_excluded.any() or omitted_path_indices:
        ax.legend(
            loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=2,
            fontsize=7, framealpha=0.9,
        )

    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return scale
