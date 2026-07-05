"""Justify CURVATURE_WINDOW_PX_PLACEHOLDER (curvature.py) with a measured
bias/variance/RMSE sweep, instead of asserting a window length from a
single eyeballed case.

Deterministic and seeded: re-running this script reproduces the exact same
table. Run from the repo root:

    python3 scripts/curvature_window_sweep.py

Method: for each (radius, jitter level, scan window) cell, generate
generate_curved_t_junction images with KNOWN ground-truth host curvature
1/radius (repeated across several seeds when jitter > 0), run them through
the real production pipeline (binarize -> skeletonize_and_prune ->
extract_graph -> compute_edge_curvature), and compare each curved host
arm's mean_abs_curvature_px_inv against 1/radius. Errors are reported as a
*relative* fraction of the true curvature (not raw px^-1), since the true
value itself spans a ~10x range across the tested radii and an absolute
RMSE would not be comparable/combinable across cells. Reports per-cell
bias/std/rmse (relative), then the worst-case (minimax) relative RMSE per
window across all tested radii/jitter levels -- that worst-case number is
what should drive the window choice.

Because generate_curved_t_junction is exactly circular (constant
curvature), this sweep validates the noise-averaging side of the
window-size tradeoff described in curvature.py's module docstring (how
much rasterization/skeleton-jitter noise gets averaged out), not the
varying-curvature-blur side (which needs a non-constant-curvature fixture
that does not exist yet -- no claim is made here about window bias on
real, non-circular crack curvature).
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.crackgraph.binarize import binarize
from src.crackgraph.curvature import compute_edge_curvature
from src.crackgraph.graph import extract_graph
from src.crackgraph.skeleton import skeletonize_and_prune
from src.crackgraph.synthetic import generate_curved_t_junction

WINDOWS = [5.0, 8.0, 10.0, 15.0, 20.0]
RADII = [15.0, 30.0, 60.0, 100.0]
JITTER_LEVELS = [0.0, 0.5, 1.0]
N_SEEDS_WHEN_JITTERED = 6

# A T-junction's host arm is a circular arc; only edges that are actually
# curved (not the straight abutter) should contribute to this sweep.
CURVED_EDGE_TORTUOSITY_MIN = 1.02


def run_sweep():
    print(f"{'radius':>7} {'jitter':>7} {'window':>7} {'bias%':>8} {'std%':>8} {'rmse%':>8}  (n_samples)")
    print("-" * 62)

    worst_rmse_per_window = {w: 0.0 for w in WINDOWS}

    for radius in RADII:
        true_kappa = 1.0 / radius
        for jitter in JITTER_LEVELS:
            n_seeds = N_SEEDS_WHEN_JITTERED if jitter > 0 else 1
            for window in WINDOWS:
                rel_errors = []
                for seed in range(n_seeds):
                    gray = generate_curved_t_junction(radius=radius, jitter_px=jitter, rng_seed=seed)
                    b = binarize(gray, sanity_band=(0.0, 1.0))
                    s = skeletonize_and_prune(b.mask, source_image=gray, spur_px=3)
                    g = extract_graph(s.skeleton)
                    r = compute_edge_curvature(s.skeleton, g, window_px=window)
                    for edge in r.edges:
                        if edge.tortuosity is None or edge.tortuosity < CURVED_EDGE_TORTUOSITY_MIN:
                            continue
                        if edge.mean_abs_curvature_px_inv is None:
                            continue
                        rel_errors.append((edge.mean_abs_curvature_px_inv - true_kappa) / true_kappa)
                if not rel_errors:
                    continue
                rel_errors = np.array(rel_errors)
                bias = float(rel_errors.mean()) * 100.0
                std = float(rel_errors.std()) * 100.0
                rmse = float(np.sqrt(np.mean(rel_errors**2))) * 100.0
                worst_rmse_per_window[window] = max(worst_rmse_per_window[window], rmse)
                print(
                    f"{radius:>7.0f} {jitter:>7.1f} {window:>7.0f} {bias:>7.1f}% {std:>7.1f}% {rmse:>7.1f}%  (n={len(rel_errors)})"
                )

    print()
    print("Worst-case (minimax) relative RMSE per window, across all radii/jitter levels:")
    tested_windows = [w for w in WINDOWS if worst_rmse_per_window[w] > 0.0]
    if not tested_windows:
        print("  no window produced any measurable curved-edge sample -- check RADII/WINDOWS")
        return
    best_window = min(tested_windows, key=worst_rmse_per_window.get)
    for w in WINDOWS:
        marker = "  <- minimax choice" if w == best_window else ""
        note = "" if worst_rmse_per_window[w] > 0.0 else "  (no samples)"
        print(f"  window_px={w:>5.0f}: worst-case RMSE = {worst_rmse_per_window[w]:6.1f}%{note}{marker}")
    print()
    print(f"Recommended CURVATURE_WINDOW_PX_PLACEHOLDER = {best_window:.0f}")


if __name__ == "__main__":
    run_sweep()
