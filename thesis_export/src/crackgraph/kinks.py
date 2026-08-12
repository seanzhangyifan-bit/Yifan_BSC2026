"""Flag-only detection of sharp interior corners ("kinks") along edges.

A sharp direction change in the *interior* of an edge is evidence that two
distinct cracks were fused into one skeleton path: the corner is a
degree-2 pixel, so skan never makes a node there and the junction logic
never sees it. Per CLAUDE.md this is the en-passant / pseudo-junction
case -- the atoms of the analysis should be growth-arcs, and a kink
suggests two arrested cracks, not one continuous crack.

This module only *flags* kinks (for the report and the overlay). It does
NOT split edges or change graph topology -- splitting alters what stage 5
will treat as atoms of the partial order and is deferred to its own task
with its own verification.

Detection uses chords, not fits, deliberately: a kink is a first-order
discontinuity in direction, which chords detect robustly; we only need
"is there a corner here", not an unbiased angle estimate.
"""

from dataclasses import dataclass

import numpy as np
import skan

from .graph import GraphResult

KINK_WINDOW_PX_PLACEHOLDER = 10.0  # 🔴 assumed — see CALIBRATION.md

KINK_TURN_DEG_PLACEHOLDER = 45.0  # 🔴 assumed — see CALIBRATION.md


@dataclass
class EdgeKink:
    path_index: int
    point_index: int  # index into skel.path_coordinates(path_index)
    coord: tuple[float, float]  # (row, col) [measured]
    turn_angle_deg: float  # [measured]


@dataclass
class KinkScanResult:
    kinks: list[EdgeKink]  # flagged only -- topology unchanged  [interpreted]
    n_edges_scanned: int  # [measured]
    window_px: float  # [PLACEHOLDER]
    min_turn_deg: float  # [PLACEHOLDER]


def find_kinks(
    skel: skan.Skeleton,
    graph_result: GraphResult,
    *,
    window_px: float = KINK_WINDOW_PX_PLACEHOLDER,
    min_turn_deg: float = KINK_TURN_DEG_PLACEHOLDER,
) -> KinkScanResult:
    """Scan every edge polyline for interior direction changes >= min_turn_deg.

    Per candidate interior point (at least window_px of arc length from
    both path ends, so junction-adjacent jitter is never scanned): the
    incoming direction is the chord over the window before it, the
    outgoing direction the chord over the window after it; the turn angle
    is the angle between the two chords (0 deg = straight). Points at or
    above min_turn_deg are flagged, then non-max suppressed (only the
    locally sharpest point within 2*window_px survives) so one physical
    kink yields one flag. Two genuine kinks closer than 2*window_px would
    merge into one flag -- accepted at this placeholder-constant stage.
    """
    summary = graph_result.summary
    kinks: list[EdgeKink] = []
    n_scanned = 0

    for path_index in summary.index:
        n_scanned += 1
        coords = skel.path_coordinates(int(path_index)).astype(np.float64)
        if len(coords) < 3:
            continue
        steps = np.linalg.norm(np.diff(coords, axis=0), axis=1)
        s = np.concatenate([[0.0], np.cumsum(steps)])
        if s[-1] < 2 * window_px:
            continue

        candidates: list[tuple[float, int]] = []
        for k in range(1, len(coords) - 1):
            if s[k] < window_px or s[-1] - s[k] < window_px:
                continue
            j_back = int(np.searchsorted(s, s[k] - window_px, side="right")) - 1
            j_fwd = int(np.searchsorted(s, s[k] + window_px, side="left"))
            v_in = coords[k] - coords[j_back]
            v_out = coords[j_fwd] - coords[k]
            n_in, n_out = np.linalg.norm(v_in), np.linalg.norm(v_out)
            if n_in < 1e-9 or n_out < 1e-9:
                continue
            cos_ang = np.clip(np.dot(v_in, v_out) / (n_in * n_out), -1.0, 1.0)
            turn = float(np.degrees(np.arccos(cos_ang)))
            if turn >= min_turn_deg:
                candidates.append((turn, k))

        # Non-max suppression: sharpest first, suppress anything within
        # 2*window_px of arc length of an already-kept kink.
        candidates.sort(reverse=True)
        kept: list[tuple[float, int]] = []
        for turn, k in candidates:
            if all(abs(s[k] - s[k_kept]) >= 2 * window_px for _, k_kept in kept):
                kept.append((turn, k))

        for turn, k in kept:
            kinks.append(
                EdgeKink(
                    path_index=int(path_index),
                    point_index=k,
                    coord=(float(coords[k][0]), float(coords[k][1])),
                    turn_angle_deg=turn,
                )
            )

    kinks.sort(key=lambda kk: (kk.coord[0], kk.coord[1]))
    return KinkScanResult(
        kinks=kinks,
        n_edges_scanned=n_scanned,
        window_px=window_px,
        min_turn_deg=min_turn_deg,
    )
