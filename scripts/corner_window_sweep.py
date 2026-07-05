"""Justify CORNER_WINDOW_PX (corners.py) with a measured bias/variance/RMSE
sweep, the same method used for ANNULUS_OUTER_PX_PLACEHOLDER
(scripts/window_sweep.py) -- not an eyeballed guess.

Deterministic and seeded. Run from the repo root:

    python3 scripts/corner_window_sweep.py

Method: for each (geometry, jitter level, corner window) cell, generate
synthetic junction images with KNOWN ground-truth arm bearings (repeated
across several seeds when jitter > 0), run them through the real corner
cross-check (find_background_contours + cross_check_junctions internals),
and compare each resolved arm bearing against its nearest ground-truth
bearing. Reports bias/std/RMSE plus the RESOLUTION RATE (fraction of
junctions where the corner count/pairing even produced an answer) per
cell, since a too-small window can fail to find corners at all -- that
failure mode matters as much as angular accuracy.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.crackgraph.binarize import binarize
from src.crackgraph.corners import _resolve_arm_bearings, _scan_contour_for_corners, find_background_contours
from src.crackgraph.graph import extract_graph
from src.crackgraph.skeleton import skeletonize_and_prune
from src.crackgraph.synthetic import generate_curved_t_junction, generate_t_junction

SEARCH_RADIUS_PX = 25.0
MIN_TURN_DEG = 45.0
WINDOWS = [3.0, 4.0, 6.0, 8.0, 10.0, 12.0]
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

    print(
        f"{'geometry':<22} {'jitter':>7} {'window':>7} {'bias':>8} {'std':>8} {'rmse':>8} "
        f"{'resolved':>10}  (deg, n_bearings)"
    )
    print("-" * 90)

    worst_rmse_per_window = {w: 0.0 for w in WINDOWS}
    worst_unresolved_per_window = {w: 0.0 for w in WINDOWS}

    for name, make, truth in geometries:
        for jitter in JITTER_LEVELS:
            n_seeds = N_SEEDS_WHEN_JITTERED if jitter > 0 else 1
            for window in WINDOWS:
                errors = []
                n_junctions = 0
                n_resolved = 0
                for seed in range(n_seeds):
                    gray = make(jitter, seed)
                    b = binarize(gray, sanity_band=(0.0, 1.0))
                    s = skeletonize_and_prune(b.mask, source_image=gray, spur_px=3)
                    g = extract_graph(s.skeleton)
                    contours = find_background_contours(s.mask_clean)
                    for node_id, degree, coord in zip(g.node_ids, g.node_degree, g.node_coords):
                        if degree != 3:
                            continue
                        n_junctions += 1
                        vertex = np.array(coord)
                        corners = []
                        for ci, c in enumerate(contours):
                            corners.extend(
                                _scan_contour_for_corners(c, ci, vertex, SEARCH_RADIUS_PX, window, MIN_TURN_DEG)
                            )
                        arm_bearings, _ = _resolve_arm_bearings(corners)
                        if arm_bearings is None:
                            continue
                        n_resolved += 1
                        for bearing in arm_bearings:
                            errors.append(_nearest_truth_error(bearing, truth))

                resolved_frac = n_resolved / n_junctions if n_junctions else 0.0
                worst_unresolved_per_window[window] = max(
                    worst_unresolved_per_window[window], 1.0 - resolved_frac
                )
                if not errors:
                    print(f"{name:<22} {jitter:>7.1f} {window:>7.0f} {'--':>8} {'--':>8} {'--':>8} {resolved_frac:>9.0%}")
                    continue
                errors = np.array(errors)
                bias = float(errors.mean())
                std = float(errors.std())
                rmse = float(np.sqrt(np.mean(errors**2)))
                worst_rmse_per_window[window] = max(worst_rmse_per_window[window], rmse)
                print(
                    f"{name:<22} {jitter:>7.1f} {window:>7.0f} {bias:>8.2f} {std:>8.2f} {rmse:>8.2f} "
                    f"{resolved_frac:>9.0%}  (n={len(errors)})"
                )

    print()
    print("Worst-case RMSE and worst-case unresolved fraction per window:")
    # Combined score: penalize both poor accuracy and failure to resolve.
    combined = {w: worst_rmse_per_window[w] + 100.0 * worst_unresolved_per_window[w] for w in WINDOWS}
    best_window = min(combined, key=combined.get)
    for w in WINDOWS:
        marker = "  <- choice" if w == best_window else ""
        print(
            f"  window={w:>5.0f}: worst-case RMSE = {worst_rmse_per_window[w]:6.2f} deg, "
            f"worst-case unresolved = {worst_unresolved_per_window[w]:5.0%}{marker}"
        )
    print()
    print(f"Recommended CORNER_WINDOW_PX = {best_window:.0f}")


if __name__ == "__main__":
    run_sweep()
