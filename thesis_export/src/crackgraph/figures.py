"""Figures for one ImageAnalysis (see analysis.py).

- render_overlay_with_regions: the skeleton on the micrograph, flaked
  regions tinted, each analysed region outlined and numbered.
- render_region_panels: one orientation rose + tortuosity histogram per
  region. For a grid, panels sit where their cell sits in the image, so
  spatial variation reads directly off the figure.
- render_region_map: one column of the region table as a colour map over
  the grid cells, drawn on the micrograph.
"""

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .analysis import ImageAnalysis
from .overlay import render_crack_stats_overlay
from .curvature import reliable_tortuosities
from .summary_plots import _plot_orientation_rose_on_ax, _plot_tortuosity_hist_on_ax

PLOT_DPI = 150
# Above this many regions the per-region panels get too small to read;
# render_region_map is the better view then.
MAX_PANEL_REGIONS = 36


def render_overlay_with_regions(analysis: ImageAnalysis, out_path: Path) -> None:
    engine = analysis.engine
    show_outlines = not (len(analysis.regions) == 1 and analysis.regions[0].is_whole_image(engine.shape))
    render_crack_stats_overlay(
        analysis.rgb, engine.skeleton.skeleton, engine.graph,
        engine.flaking.excluded_mask, engine.omitted, out_path,
        regions=analysis.regions if show_outlines else None,
    )


def _shared_tortuosity_bins(analysis: ImageAnalysis):
    """One set of bin edges for every region's histogram, so panels can be
    compared by eye instead of each rescaling to its own range."""
    values = [t for cr in analysis.curvature.values() for t in reliable_tortuosities(cr)]
    if values and max(values) > min(values):
        return np.linspace(min(values), max(values), 16)
    return 15


def _panel_layout(analysis: ImageAnalysis) -> tuple[int, int, list[tuple[int, int]]]:
    """(n_rows, n_cols, [(row, col) per region]) for the panel grid."""
    spec = analysis.settings.regions
    if spec.mode == "grid":
        positions = []
        for region in analysis.regions:
            number = int(region.label.split()[1])
            positions.append(((number - 1) // spec.n_cols, (number - 1) % spec.n_cols))
        return spec.n_rows, spec.n_cols, positions
    n = len(analysis.regions)
    return 1, n, [(0, i) for i in range(n)]


def render_region_panels(analysis: ImageAnalysis, out_path: Path) -> bool:
    """Rose + tortuosity panel per region. Returns False (and writes
    nothing) if there is nothing to draw or too many regions to read."""
    has_rose = bool(analysis.anisotropy)
    has_tort = bool(analysis.curvature)
    if not (has_rose or has_tort) or len(analysis.regions) > MAX_PANEL_REGIONS:
        return False
    n_rows, n_cols, positions = _panel_layout(analysis)
    per_panel = int(has_rose) + int(has_tort)
    fig = plt.figure(figsize=(2.2 * n_cols, 2.2 * n_rows * per_panel), dpi=PLOT_DPI)
    grid = fig.add_gridspec(n_rows * per_panel, n_cols, hspace=0.7, wspace=0.4)
    bins = _shared_tortuosity_bins(analysis) if has_tort else None
    for region, (r, c) in zip(analysis.regions, positions):
        k = r * per_panel
        name = region.label.split(" (")[0]
        if has_rose:
            ax = fig.add_subplot(grid[k, c], projection="polar")
            _plot_orientation_rose_on_ax(ax, analysis.anisotropy[region.label], fontsize=6, compact=True)
            ax.set_title(f"{name}\n{ax.get_title()}", fontsize=6)
            k += 1
        if has_tort:
            ax = fig.add_subplot(grid[k, c])
            _plot_tortuosity_hist_on_ax(ax, analysis.curvature[region.label], fontsize=6, compact=True, bins=bins)
            if not has_rose:
                ax.set_title(f"{name}: tortuosity", fontsize=6)
    fig.suptitle(f"{analysis.image_path.name}: per-region orientation and tortuosity", fontsize=8)
    fig.savefig(out_path, dpi=PLOT_DPI, bbox_inches="tight")
    plt.close(fig)
    return True


def render_region_map(analysis: ImageAnalysis, column: str, out_path: Path) -> bool:
    """Colour map of one numeric column over the analysed regions, on a
    faded copy of the micrograph. Returns False if the column is missing."""
    values = [row.get(column) for row in analysis.rows]
    if any(v is None for v in values):
        return False
    h, w = analysis.engine.shape
    scale = min(1.0, 1200 / max(h, w))
    step = max(1, int(round(1 / scale)))
    background = analysis.rgb[::step, ::step]
    fig, ax = plt.subplots(figsize=(7, 7 * h / w), dpi=PLOT_DPI)
    ax.imshow(background, extent=(0, w, h, 0), alpha=0.5)
    finite = [v for v in values if isinstance(v, (int, float)) and math.isfinite(v)]
    vmin, vmax = (min(finite), max(finite)) if finite else (0.0, 1.0)
    cmap = plt.get_cmap("viridis")
    norm = matplotlib.colors.Normalize(vmin=vmin, vmax=vmax if vmax > vmin else vmin + 1e-9)
    for region, v in zip(analysis.regions, values):
        ok = isinstance(v, (int, float)) and math.isfinite(v)
        ax.add_patch(plt.Rectangle(
            (region.col_start, region.row_start),
            region.col_stop - region.col_start, region.row_stop - region.row_start,
            facecolor=cmap(norm(v)) if ok else "none", alpha=0.6, edgecolor="white", linewidth=0.5,
        ))
        ax.text(
            (region.col_start + region.col_stop) / 2, (region.row_start + region.row_stop) / 2,
            f"{v:.3g}" if ok else "n/a", ha="center", va="center", fontsize=6, color="white",
        )
    ax.set_xlim(0, w)
    ax.set_ylim(h, 0)
    ax.axis("off")
    fig.colorbar(matplotlib.cm.ScalarMappable(norm=norm, cmap=cmap), ax=ax, fraction=0.035, label=column)
    ax.set_title(f"{analysis.image_path.name}: {column} per region", fontsize=8)
    fig.savefig(out_path, dpi=PLOT_DPI, bbox_inches="tight")
    plt.close(fig)
    return True
