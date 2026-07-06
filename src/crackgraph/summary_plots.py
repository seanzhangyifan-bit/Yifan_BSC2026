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

from .anisotropy import AnisotropyResult
from .curvature import CurvatureScanResult

ROSE_FIGSIZE = (2.4, 2.4)
CURVATURE_HIST_FIGSIZE = (4.0, 2.0)
PLOT_DPI = 150


def _plot_orientation_rose_on_ax(ax, anisotropy_result: AnisotropyResult, *, fontsize: float = 7) -> None:
    """Draw the mirrored-axial orientation rose onto a pre-built polar
    Axes. Shared by render_orientation_rose (one figure per chunk) and
    render_overview_figure (one row per section in a single figure) so the
    axial-mirroring logic and no-data handling exist in exactly one place.
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
    ax_tort, ax_curv, curvature_result: CurvatureScanResult, *, fontsize: float = 6
) -> None:
    """Draw the tortuosity + mean|curvature| histograms onto two pre-built
    Axes. Shared by render_curvature_histogram and render_overview_figure --
    see _plot_orientation_rose_on_ax for why this is factored out.
    """
    tortuosities = [e.tortuosity for e in curvature_result.edges if e.tortuosity is not None]
    mean_kappas = [
        e.mean_abs_curvature_px_inv for e in curvature_result.edges if e.mean_abs_curvature_px_inv is not None
    ]

    if tortuosities:
        ax_tort.hist(tortuosities, bins=15, color="tab:blue")
    else:
        ax_tort.text(0.5, 0.5, "no data", ha="center", va="center", transform=ax_tort.transAxes, fontsize=fontsize)
    ax_tort.set_title("tortuosity (arc/chord)  [measured]", fontsize=fontsize)
    ax_tort.tick_params(labelsize=fontsize - 1)

    if mean_kappas:
        ax_curv.hist(mean_kappas, bins=15, color="tab:orange")
    else:
        ax_curv.text(0.5, 0.5, "no data", ha="center", va="center", transform=ax_curv.transAxes, fontsize=fontsize)
    ax_curv.set_title("mean |curvature| (1/px)  [measured]", fontsize=fontsize)
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


def render_overview_figure(
    sections: list[tuple[str, AnisotropyResult, CurvatureScanResult]],
    whole_image: tuple[str, AnisotropyResult, CurvatureScanResult],
    out_path: str | Path,
) -> None:
    """Compile every section's rose diagram + curvature histogram, plus
    the whole-image result, into one figure: a flat list of rows (rose |
    tortuosity-hist | curvature-hist), one row per section, whole-image
    appended as the final row. A spatial contact-sheet layout (panels
    placed at each section's actual position in the image) was considered
    and deliberately not used -- a flat list was chosen instead for
    simplicity (see scripts/overview_figure.py and CLAUDE.md).
    """
    rows = list(sections) + [whole_image]
    n_rows = len(rows)
    fig = plt.figure(figsize=(9.0, 1.8 * n_rows), dpi=PLOT_DPI)
    gs = fig.add_gridspec(n_rows, 3, width_ratios=[1.0, 1.0, 1.0])

    row_labels_and_axes = []
    for i, (label, anisotropy_result, curvature_result) in enumerate(rows):
        ax_rose = fig.add_subplot(gs[i, 0], projection="polar")
        ax_tort = fig.add_subplot(gs[i, 1])
        ax_curv = fig.add_subplot(gs[i, 2])
        _plot_orientation_rose_on_ax(ax_rose, anisotropy_result, fontsize=6)
        _plot_curvature_hist_on_axes(ax_tort, ax_curv, curvature_result, fontsize=5)
        row_labels_and_axes.append((label, ax_rose))

    # Reserve left margin for row labels, then place them using each rose
    # axis's *post-layout* position -- computing positions before
    # tight_layout would make the labels drift once it re-flows the grid.
    fig.tight_layout(rect=(0.06, 0.0, 1.0, 1.0))
    for label, ax_rose in row_labels_and_axes:
        row_center_y = (ax_rose.get_position().y0 + ax_rose.get_position().y1) / 2.0
        fig.text(0.005, row_center_y, label, va="center", ha="left", fontsize=8, rotation=90)

    fig.savefig(out_path, dpi=PLOT_DPI, bbox_inches="tight")
    plt.close(fig)
