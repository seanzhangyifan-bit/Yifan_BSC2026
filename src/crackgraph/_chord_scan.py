"""Shared chord-pair scanning geometry for per-edge polyline analysis.

Extracted from the scan loop in kinks.py (find_kinks): given a polyline's
pixel coordinates and cumulative arc length, find the incoming/outgoing
chord vectors spanning `window_px` on each side of a point. kinks.py and
corners.py keep their own inline copies of this logic (each already tested
and working) -- this module exists so curvature.py and anisotropy.py, a
third and fourth consumer, don't triplicate/quadruplicate it. Retrofitting
kinks.py/corners.py onto this module is a separate follow-up task, not
part of adding the two new analyses.
"""

import numpy as np


def arc_length(coords: np.ndarray) -> np.ndarray:
    """Cumulative arc length along a polyline. s[0] = 0."""
    steps = np.linalg.norm(np.diff(coords, axis=0), axis=1)
    return np.concatenate([[0.0], np.cumsum(steps)])


def chord_pair_at(
    coords: np.ndarray, s: np.ndarray, k: int, window_px: float
) -> tuple[np.ndarray, np.ndarray] | None:
    """Incoming/outgoing chord vectors spanning window_px on each side of
    point index k, using the same searchsorted logic as kinks.py's scan.

    Returns None if k is within window_px of either path end (no room for
    a full window on that side), or if either chord has ~zero length.
    """
    if s[k] < window_px or s[-1] - s[k] < window_px:
        return None
    j_back = int(np.searchsorted(s, s[k] - window_px, side="right")) - 1
    j_fwd = int(np.searchsorted(s, s[k] + window_px, side="left"))
    v_in = coords[k] - coords[j_back]
    v_out = coords[j_fwd] - coords[k]
    if np.linalg.norm(v_in) < 1e-9 or np.linalg.norm(v_out) < 1e-9:
        return None
    return v_in, v_out


def suppress_non_max(
    candidates: list[tuple[float, int]], s: np.ndarray, suppress_radius_px: float
) -> list[tuple[float, int]]:
    """Greedy sharpest-first non-max suppression: keep a candidate only if
    it is at least suppress_radius_px of arc length away (in s) from every
    already-kept candidate. candidates are (score, point_index) pairs;
    higher score is sharper/kept first. Same logic as kinks.py's scan.
    """
    ordered = sorted(candidates, reverse=True)
    kept: list[tuple[float, int]] = []
    for score, k in ordered:
        if all(abs(s[k] - s[k_kept]) >= suppress_radius_px for _, k_kept in kept):
            kept.append((score, k))
    return kept
