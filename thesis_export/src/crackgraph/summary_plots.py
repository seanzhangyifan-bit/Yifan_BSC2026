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
from .curvature import CurvatureScanResult, reliable_tortuosities

ROSE_FIGSIZE = (2.4, 2.4)
CURVATURE_HIST_FIGSIZE = (4.0, 2.0)
PLOT_DPI = 150




def _plot_orientation_rose_on_ax(
    ax, anisotropy_result: AnisotropyResult, *, fontsize: float = 7, compact: bool = False
) -> None:
    """Draw the mirrored-axial orientation rose onto a pre-built polar
    Axes. Shared by render_orientation_rose (one figure per chunk) and
    figures.render_region_panels (one panel per region) so the
    axial-mirroring logic and no-data handling exist in exactly one place.

    `compact=True` (used for figures.py's small per-region panels) drops the boilerplate title wording and the radial tick
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
        ax.set_title(f"n={anisotropy_result.n_samples}", fontsize=fontsize)
        ax.set_yticklabels([])
    else:
        ax.set_title("crack directions (axial, mirrored)  [measured]", fontsize=fontsize)
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


def _plot_tortuosity_hist_on_ax(
    ax_tort,
    curvature_result: CurvatureScanResult,
    *,
    fontsize: float = 6,
    compact: bool = False,
    bins: np.ndarray | int = 15,
) -> None:
    """Draw just the tortuosity histogram onto a pre-built Axes. Split out
    from _plot_curvature_hist_on_axes so figures.py's per-region panels
    can show tortuosity alone.

    `bins` defaults to 15 (matplotlib auto-ranges to that Axes' own data,
    render_curvature_histogram's behavior, unchanged). figures.render_region_panels
    instead passes shared bin edges (an array) computed once across every
    cluster in the figure, so tortuosity is visually comparable panel to
    panel instead of each panel silently rescaling to its own range.
    """
    tortuosities = reliable_tortuosities(curvature_result)
    tort_title = "tortuosity" if compact else "tortuosity (arc/chord)  [measured]"

    if tortuosities:
        ax_tort.hist(tortuosities, bins=bins, color="tab:blue")
    else:
        ax_tort.text(0.5, 0.5, "no data", ha="center", va="center", transform=ax_tort.transAxes, fontsize=fontsize)
    if isinstance(bins, np.ndarray):
        ax_tort.set_xlim(bins[0], bins[-1])
    ax_tort.set_title(tort_title, fontsize=fontsize)
    ax_tort.tick_params(labelsize=fontsize - 1)


def _plot_curvature_hist_on_axes(
    ax_tort, ax_curv, curvature_result: CurvatureScanResult, *, fontsize: float = 6, compact: bool = False
) -> None:
    """Draw the tortuosity + mean|curvature| histograms onto two pre-built
    Axes. Shared by render_curvature_histogram and figures.py --
    see _plot_orientation_rose_on_ax for why this is factored out and what
    `compact` does.
    """
    _plot_tortuosity_hist_on_ax(ax_tort, curvature_result, fontsize=fontsize, compact=compact)

    mean_kappas = [
        e.mean_abs_curvature_px_inv for e in curvature_result.edges if e.mean_abs_curvature_px_inv is not None
    ]
    curv_title = "|curvature|" if compact else "mean |curvature| (1/px)  [measured]"

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
