"""Justify ANNULUS_OUTER_PX_PLACEHOLDER (junctions.py) with a measured
bias/variance/RMSE sweep, instead of asserting a window length from a
single eyeballed census.

Deterministic and seeded: re-running this script reproduces the exact same
table. Run from the repo root:

    python3 scripts/window_sweep.py

Method: for each (geometry, jitter level, fit window) cell, generate
synthetic junction images with KNOWN ground-truth arm bearings (repeated
across several seeds when jitter > 0), run them through the real
production pipeline (binarize -> skeletonize_and_prune -> extract_graph ->
classify_junctions), and compare each recovered EdgeDirection.bearing_deg
against its nearest ground-truth bearing. Reports per-cell bias
(mean signed error), std, and RMSE in degrees, then the worst-case
(minimax) RMSE per window across all tested geometries and jitter levels
-- that worst-case number is what should drive the window choice, since
the pipeline must work across the whole dataset, not just its easiest case.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.crackgraph.binarize import binarize
from src.crackgraph.graph import extract_graph
from src.crackgraph.junctions import classify_junctions
from src.crackgraph.skeleton import skeletonize_and_prune
from src.crackgraph.synthetic import generate_curved_t_junction, generate_t_junction

INNER_RADIUS_PX = 5.0
WINDOWS = [20.0, 30.0, 40.0, 60.0, 80.0]
JITTER_LEVELS = [0.0, 0.5, 1.0]
N_SEEDS_WHEN_JITTERED = 6


def _straight_t_geometry(angle_deg):
    name = f"straight_T_angle={angle_deg:.0f}"

    def make(jitter_px, seed):
        return generate_t_junction(angle_deg=angle_deg, jitter_px=jitter_px, rng_seed=seed)

    ground_truth_bearings = [0.0, 180.0, 180.0 - angle_deg]
    return name, make, ground_truth_bearings


def _curved_t_geometry(radius):
    name = f"curved_T_radius={radius:.0f}"

    def make(jitter_px, seed):
        return generate_curved_t_junction(radius=radius, jitter_px=jitter_px, rng_seed=seed)

    ground_truth_bearings = [0.0, 180.0, -90.0]
    return name, make, ground_truth_bearings


def _angular_diff(a, b):
    return (a - b + 180.0) % 360.0 - 180.0


def _nearest_truth_error(bearing, truth_bearings):
    diffs = [_angular_diff(bearing, t) for t in truth_bearings]
    return min(diffs, key=abs)


def run_sweep():
    geometries = [
        _straight_t_geometry(60.0),
        _straight_t_geometry(90.0),
        _straight_t_geometry(120.0),
        _curved_t_geometry(60.0),
        _curved_t_geometry(30.0),
    ]

    print(f"{'geometry':<22} {'jitter':>7} {'window':>7} {'bias':>8} {'std':>8} {'rmse':>8}  (deg, n_samples)")
    print("-" * 80)

    worst_rmse_per_window = {w: 0.0 for w in WINDOWS}

    for name, make, truth in geometries:
        for jitter in JITTER_LEVELS:
            n_seeds = N_SEEDS_WHEN_JITTERED if jitter > 0 else 1
            for window in WINDOWS:
                errors = []
                for seed in range(n_seeds):
                    gray = make(jitter, seed)
                    b = binarize(gray, sanity_band=(0.0, 1.0))
                    s = skeletonize_and_prune(b.mask, source_image=gray, spur_px=3)
                    g = extract_graph(s.skeleton)
                    r = classify_junctions(
                        s.skeleton, g, inner_radius_px=INNER_RADIUS_PX, outer_radius_px=window
                    )
                    for c in r.classifications:
                        for ed in c.edge_directions:
                            if ed.bearing_deg is not None:
                                errors.append(_nearest_truth_error(ed.bearing_deg, truth))
                if not errors:
                    continue
                errors = np.array(errors)
                bias = float(errors.mean())
                std = float(errors.std())
                rmse = float(np.sqrt(np.mean(errors**2)))
                worst_rmse_per_window[window] = max(worst_rmse_per_window[window], rmse)
                print(
                    f"{name:<22} {jitter:>7.1f} {window:>7.0f} {bias:>8.2f} {std:>8.2f} {rmse:>8.2f}  (n={len(errors)})"
                )

    print()
    print("Worst-case (minimax) RMSE per window, across all geometries/jitter levels:")
    best_window = min(worst_rmse_per_window, key=worst_rmse_per_window.get)
    for w in WINDOWS:
        marker = "  <- minimax choice" if w == best_window else ""
        print(f"  outer_radius_px={w:>5.0f}: worst-case RMSE = {worst_rmse_per_window[w]:6.2f} deg{marker}")
    print()
    print(f"Recommended ANNULUS_OUTER_PX_PLACEHOLDER = {best_window:.0f}")


if __name__ == "__main__":
    run_sweep()
