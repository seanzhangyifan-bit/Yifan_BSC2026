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
    bin_edges = anisotropy_result.histogram_bin_edges_deg
    counts = anisotropy_result.histogram_weighted_counts
    bin_centers_deg = (bin_edges[:-1] + bin_edges[1:]) / 2.0
    bin_width_rad = np.radians(bin_edges[1] - bin_edges[0])

    theta = np.radians(bin_centers_deg)
    theta_mirrored = np.concatenate([theta, theta + np.pi])
    counts_mirrored = np.concatenate([counts, counts])

    fig, ax = plt.subplots(figsize=ROSE_FIGSIZE, dpi=PLOT_DPI, subplot_kw={"projection": "polar"})
    ax.set_theta_zero_location("E")
    ax.set_theta_direction(1)
    ax.bar(theta_mirrored, counts_mirrored, width=bin_width_rad, color="tab:blue", edgecolor="white", linewidth=0.3)
    ax.set_title(
        f"orientation rose (axial, mirrored)  [measured]\n"
        f"A={anisotropy_result.anisotropy_index:.2f}, dominant={anisotropy_result.dominant_bearing_deg:.0f} deg",
        fontsize=7,
    )
    ax.tick_params(labelsize=6)
    fig.savefig(out_path, dpi=PLOT_DPI, bbox_inches="tight")
    plt.close(fig)


def render_curvature_histogram(curvature_result: CurvatureScanResult, out_path: str | Path) -> None:
    """Two side-by-side histograms: per-edge tortuosity and per-edge
    mean|curvature|. Side-by-side, not overlaid, because tortuosity
    (dimensionless, range ~[1, inf)) and curvature (units 1/px) have
    incompatible x-axis scales -- overlaying would force a shared,
    misleading x-range.
    """
    tortuosities = [e.tortuosity for e in curvature_result.edges if e.tortuosity is not None]
    mean_kappas = [
        e.mean_abs_curvature_px_inv for e in curvature_result.edges if e.mean_abs_curvature_px_inv is not None
    ]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=CURVATURE_HIST_FIGSIZE, dpi=PLOT_DPI)

    if tortuosities:
        ax1.hist(tortuosities, bins=15, color="tab:blue")
    else:
        ax1.text(0.5, 0.5, "no data", ha="center", va="center", transform=ax1.transAxes, fontsize=7)
    ax1.set_title("tortuosity (arc/chord)  [measured]", fontsize=6)
    ax1.tick_params(labelsize=6)

    if mean_kappas:
        ax2.hist(mean_kappas, bins=15, color="tab:orange")
    else:
        ax2.text(0.5, 0.5, "no data", ha="center", va="center", transform=ax2.transAxes, fontsize=7)
    ax2.set_title("mean |curvature| (1/px)  [measured]", fontsize=6)
    ax2.tick_params(labelsize=6)

    fig.tight_layout()
    fig.savefig(out_path, dpi=PLOT_DPI, bbox_inches="tight")
    plt.close(fig)
