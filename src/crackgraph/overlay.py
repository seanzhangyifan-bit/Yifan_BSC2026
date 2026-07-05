"""Overlay rendering: skeleton + junction/endpoint markers on the original image.

Analysis always runs at the full resolution of the region being processed.
Only this saved visualization is downsampled, and only the *image
background* is resampled (LANCZOS) -- skeleton/node coordinates are scaled
numerically instead of resampling the (often 1px-wide) skeleton bitmap,
which would blur or break under any resampling filter.
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
    """Save an overlay PNG. Returns the scale factor used for the display image."""
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
        for i in range(n_edges):
            coords = skel.path_coordinates(i) * scale  # (row, col)
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
        ax.legend(loc="upper right", fontsize=6, markerscale=1.5, framealpha=0.7)

    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return scale
