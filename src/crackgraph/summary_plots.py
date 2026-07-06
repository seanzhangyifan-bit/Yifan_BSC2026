"""Summary-statistic plots for a single analyzed chunk: an orientation rose
diagram (from anisotropy.py's histogram) and a curvature/tortuosity
distribution histogram (from curvature.py's per-edge results).

Separate from overlay.py deliberately: overlay.py draws the skeleton and
junction markers *on the micrograph itself* (a spatial diagnostic); these
two functions instead summarize a *distribution* of measured values across
the whole chunk, with no image background at all. Same rendering idiom as
overlay.py (Agg backend, build a Figure, save it, close it, return None) --
no reusable Figure-return convention exists in this codebase, so neither
function returns anything beyond writing out_path.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from .anisotropy import AnisotropyResult
from .curvature import CurvatureScanResult

ROSE_FIGSIZE = (2.4, 2.4)
CURVATURE_HIST_FIGSIZE = (4.0, 2.0)
PLOT_DPI = 150
OVERVIEW_FIGSIZE = (13.0, 9.0)
WHOLE_IMAGE_DISPLAY_MAX_DIM_PX = 900


def _resize_for_display(rgb: np.ndarray, max_dim: int) -> np.ndarray:
    """Downsample an RGB array for display only, preserving aspect ratio --
    same idiom as overlay.py::render_overlay's display-image resize (kept
    local here rather than imported, to avoid a dependency into overlay.py,
    which has unrelated in-flight edits elsewhere)."""
    h, w = rgb.shape[:2]
    scale = min(1.0, max_dim / max(h, w))
    if scale >= 1.0:
        return rgb
    new_size = (round(w * scale), round(h * scale))
    return np.asarray(Image.fromarray(rgb).resize(new_size, Image.LANCZOS))


def _plot_orientation_rose_on_ax(
    ax, anisotropy_result: AnisotropyResult, *, fontsize: float = 7, compact: bool = False
) -> None:
    """Draw the mirrored-axial orientation rose onto a pre-built polar
    Axes. Shared by render_orientation_rose (one figure per chunk) and
    render_overview_figure (one row per section in a single figure) so the
    axial-mirroring logic and no-data handling exist in exactly one place.

    `compact=True` (used inside render_overview_figure's small corner
    clusters) drops the boilerplate title wording and the radial tick
    labels -- at that panel size the full title text overflows into
    neighboring axes.
    """
    bin_edges = anisotropy_result.histogram_bin_edges_deg
    counts = anisotropy_result.histogram_weighted_counts
    bin_centers_deg = (bin_edges[:-1] + bin_edges[1:]) / 2.0
    bin_width_rad = np.radians(bin_edges[1] - bin_edges[0])

    theta = np.radians(bin_centers_deg)
    theta_mirrored = np.concatenate([theta, theta + np.pi])
    counts_mirrored = np.concatenate([counts, counts])

    ax.set_theta_zero_location("E")
    ax.set_theta_direction(1)
    ax.bar(theta_mirrored, counts_mirrored, width=bin_width_rad, color="tab:blue", edgecolor="white", linewidth=0.3)
    if compact:
        ax.set_title(
            f"A={anisotropy_result.anisotropy_index:.2f}, dom={anisotropy_result.dominant_bearing_deg:.0f}°",
            fontsize=fontsize,
        )
        ax.set_yticklabels([])
    else:
        ax.set_title(
            f"orientation rose (axial, mirrored)  [measured]\n"
            f"A={anisotropy_result.anisotropy_index:.2f}, dominant={anisotropy_result.dominant_bearing_deg:.0f} deg",
            fontsize=fontsize,
        )
    ax.tick_params(labelsize=fontsize - 1)


def render_orientation_rose(anisotropy_result: AnisotropyResult, out_path: str | Path) -> None:
    """Polar bar plot of the length-weighted orientation histogram.

    The histogram bins are axial (0-180 deg, per anisotropy.py's doubled
    -angle convention): a crack at 10 deg and one at 190 deg are the same
    direction. Plotting only a 0-180 deg wedge would misleadingly read as
    "no data on the other side" for a quantity that is inherently
    symmetric, so each bar is mirrored onto the opposite semicircle
    (theta and theta+180) -- the conventional way axial/orientation data
    is displayed as a rose diagram in the structural-geology fracture
    -trace literature this method is drawn from (see anisotropy.py's
    [cited] attribution). Bearing convention (0 deg = east/+col) matches
    anisotropy.py's _bearing_deg exactly, via theta_zero_location="E" and
    a counterclockwise theta direction.
    """
    fig, ax = plt.subplots(figsize=ROSE_FIGSIZE, dpi=PLOT_DPI, subplot_kw={"projection": "polar"})
    _plot_orientation_rose_on_ax(ax, anisotropy_result)
    fig.savefig(out_path, dpi=PLOT_DPI, bbox_inches="tight")
    plt.close(fig)


def _plot_curvature_hist_on_axes(
    ax_tort, ax_curv, curvature_result: CurvatureScanResult, *, fontsize: float = 6, compact: bool = False
) -> None:
    """Draw the tortuosity + mean|curvature| histograms onto two pre-built
    Axes. Shared by render_curvature_histogram and render_overview_figure --
    see _plot_orientation_rose_on_ax for why this is factored out and what
    `compact` does.
    """
    tortuosities = [e.tortuosity for e in curvature_result.edges if e.tortuosity is not None]
    mean_kappas = [
        e.mean_abs_curvature_px_inv for e in curvature_result.edges if e.mean_abs_curvature_px_inv is not None
    ]
    tort_title = "tortuosity" if compact else "tortuosity (arc/chord)  [measured]"
    curv_title = "|curvature|" if compact else "mean |curvature| (1/px)  [measured]"

    if tortuosities:
        ax_tort.hist(tortuosities, bins=15, color="tab:blue")
    else:
        ax_tort.text(0.5, 0.5, "no data", ha="center", va="center", transform=ax_tort.transAxes, fontsize=fontsize)
    ax_tort.set_title(tort_title, fontsize=fontsize)
    ax_tort.tick_params(labelsize=fontsize - 1)

    if mean_kappas:
        ax_curv.hist(mean_kappas, bins=15, color="tab:orange")
    else:
        ax_curv.text(0.5, 0.5, "no data", ha="center", va="center", transform=ax_curv.transAxes, fontsize=fontsize)
    ax_curv.set_title(curv_title, fontsize=fontsize)
    ax_curv.tick_params(labelsize=fontsize - 1)


def render_curvature_histogram(curvature_result: CurvatureScanResult, out_path: str | Path) -> None:
    """Two side-by-side histograms: per-edge tortuosity and per-edge
    mean|curvature|. Side-by-side, not overlaid, because tortuosity
    (dimensionless, range ~[1, inf)) and curvature (units 1/px) have
    incompatible x-axis scales -- overlaying would force a shared,
    misleading x-range.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=CURVATURE_HIST_FIGSIZE, dpi=PLOT_DPI)
    _plot_curvature_hist_on_axes(ax1, ax2, curvature_result)
    fig.tight_layout()
    fig.savefig(out_path, dpi=PLOT_DPI, bbox_inches="tight")
    plt.close(fig)


def _add_cluster(fig, gs_slice, label: str, anisotropy_result: AnisotropyResult, curvature_result: CurvatureScanResult) -> None:
    """One rose + tortuosity-hist + curvature-hist cluster (1 row x 3
    sub-columns of the given GridSpec slice), labeled via a prefix on the
    tortuosity axis's title -- avoids changing the shared helpers' own
    title-setting logic."""
    sub_gs = gs_slice.subgridspec(1, 3, wspace=0.6)
    ax_rose = fig.add_subplot(sub_gs[0, 0], projection="polar")
    ax_tort = fig.add_subplot(sub_gs[0, 1])
    ax_curv = fig.add_subplot(sub_gs[0, 2])
    _plot_orientation_rose_on_ax(ax_rose, anisotropy_result, fontsize=6, compact=True)
    _plot_curvature_hist_on_axes(ax_tort, ax_curv, curvature_result, fontsize=6, compact=True)
    ax_tort.set_title(f"{label}\n{ax_tort.get_title()}", fontsize=6)


def render_overview_figure(
    sections: list[tuple[str, AnisotropyResult, CurvatureScanResult]],
    whole_image_rgb: np.ndarray,
    whole_image_result: tuple[str, AnisotropyResult, CurvatureScanResult],
    out_path: str | Path,
) -> None:
    """Spatial layout for exactly a 2x2 quadrant grid (not a generic N x M
    layout -- see CLAUDE.md): a big display of the whole raw micrograph in
    the center, each quadrant's rose+tortuosity+curvature cluster in the
    figure corner matching that quadrant's actual position in the source
    image, and the whole image's *own* rose+tortuosity+curvature cluster
    (its analysis result, distinct from the raw-image display) in a row
    below everything.

    `sections` must be the 4 quadrants in grid_tiles' row-major order:
    r0c0, r0c1, r1c0, r1c1 (top-left, top-right, bottom-left, bottom-right).
    """
    assert len(sections) == 4, "render_overview_figure expects exactly 4 (2x2) sections"
    r0c0, r0c1, r1c0, r1c1 = sections

    fig = plt.figure(figsize=OVERVIEW_FIGSIZE, dpi=PLOT_DPI, constrained_layout=True)
    gs = fig.add_gridspec(3, 9, height_ratios=[1.0, 1.0, 1.0], hspace=0.5)

    _add_cluster(fig, gs[0, 0:3], *r0c0)
    _add_cluster(fig, gs[0, 6:9], *r0c1)
    _add_cluster(fig, gs[1, 0:3], *r1c0)
    _add_cluster(fig, gs[1, 6:9], *r1c1)

    ax_img = fig.add_subplot(gs[0:2, 3:6])
    ax_img.imshow(_resize_for_display(whole_image_rgb, WHOLE_IMAGE_DISPLAY_MAX_DIM_PX))
    ax_img.axis("off")
    ax_img.set_title("whole image (raw)  [measured]", fontsize=8)

    _add_cluster(fig, gs[2, 0:9], *whole_image_result)

    fig.savefig(out_path, dpi=PLOT_DPI)
    plt.close(fig)
