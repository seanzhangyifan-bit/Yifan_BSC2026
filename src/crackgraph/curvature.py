"""Per-edge curvature and tortuosity: how bent an individual crack segment is.

This is a geometry measurement, not a chronology one -- it says nothing
about growth order and does not touch the junction/poset machinery. It
answers a different question from junctions.py's annulus tangent fit:
junctions.py measures a *signed* curvature at a single point (the vertex,
s=0) on one arm, as a byproduct of T/Y classification. This module instead
scans the *whole* edge and reports an *unsigned* curvature profile plus a
scale-invariant tortuosity, using the same chord-pair-turn-angle geometry
as kinks.py's scan (see _chord_scan.py) but run continuously rather than
thresholded/flagged: kinks.py asks "is there a sharp corner here" (evidence
of two fused cracks); this module asks "how much does this one edge bend,
overall and locally".

Two numbers are reported per edge because they catch different things: a
long smooth bend and several small sharp wiggles can have similar
tortuosity but very different mean curvature (see test_curvature.py's
kinked-line case) -- per CLAUDE.md's "chronometers can disagree
informatively" ethos, both are kept rather than collapsed into one.

Known limitation: for a path of *constant* curvature (a true circular
arc), the chord-pair estimator below is essentially exact at any window
size -- the chord from s-w to s is exactly parallel to the tangent at the
arc's midpoint s-w/2 for any w on a circle, so the window only ever
determines how much rasterization/skeleton-jitter noise gets averaged
over, not a systematic bias. That is not true for a path whose curvature
*varies* along its length (real cracks, generically): there, a large
window blurs together genuinely different local curvatures into one
number, the same bias/smoothing tradeoff documented for the annulus fit
in junctions.py / generate_curved_t_junction. The window is therefore a
real bias-vs-jitter-noise tradeoff on real (non-constant-curvature) data,
to be *measured* via scripts/curvature_window_sweep.py -- which, because
generate_curved_t_junction is exactly circular, can only validate the
noise-averaging side of that tradeoff, not the varying-curvature blur; it
sweeps window_px against generate_curved_t_junction's exact known 1/radius
at several jitter levels for that reason.
"""

from dataclasses import dataclass

import numpy as np
import skan

from ._chord_scan import arc_length, chord_pair_at
from .graph import GraphResult

CURVATURE_WINDOW_PX_PLACEHOLDER = 10.0
# [PLACEHOLDER] chord window (arc length) on each side of each scan point.
# Same jitter-averaging scale reasoning as kinks.py's KINK_WINDOW_PX_PLACEHOLDER
# and junctions.py's annulus radii; not derived from calibrated h/um-per-px
# (none exists yet, so this is still a pixel-space placeholder, not a
# um/h-anchored value). scripts/curvature_window_sweep.py's minimax sweep
# over windows [5,8,10,15,20] px, radii [15,30,60,100] px, jitter [0,0.5,1]
# px picked window_px=10 (worst-case relative RMSE 86%, at radius=15/
# jitter=1.0 -- a small-radius, heavily-jittered stress case; RMSE is much
# lower, <25%, across the rest of the sweep). Re-run the script if the
# tested radius/jitter range should change.

CHORD_LENGTH_EPS_PX = 1.0
# [PLACEHOLDER] below one pixel of start-to-end separation, arc/chord is
# dominated by discretization noise rather than measuring anything -- report
# tortuosity=None instead of a huge or infinite number.


@dataclass
class EdgeCurvature:
    path_index: int
    arc_length_px: float  # [measured]
    chord_length_px: float  # [measured] straight-line distance, endpoint to endpoint
    tortuosity: float | None  # arc/chord [measured]; None if chord_length_px too small
    s_samples: np.ndarray | None  # [measured] arc-length position of each profile point
    curvature_profile_px_inv: np.ndarray | None  # [measured] kappa(s); None if edge < 2*window_px
    mean_abs_curvature_px_inv: float | None  # [measured]
    max_abs_curvature_px_inv: float | None  # [measured]
    ok: bool
    failure_reason: str | None


@dataclass
class CurvatureScanResult:
    edges: list[EdgeCurvature]
    n_edges_scanned: int  # [measured]
    window_px: float  # [PLACEHOLDER]


def compute_edge_curvature(
    skel: skan.Skeleton,
    graph_result: GraphResult,
    *,
    window_px: float = CURVATURE_WINDOW_PX_PLACEHOLDER,
) -> CurvatureScanResult:
    """Scan every edge polyline for tortuosity and a local curvature profile.

    Tortuosity (arc_length / chord_length) is computed for every edge with
    a non-degenerate chord, independent of window_px -- even a 2-point edge
    has a tortuosity. The windowed curvature profile additionally requires
    at least 2*window_px of arc length (same requirement as kinks.py's
    scan); shorter edges get tortuosity but curvature_profile_px_inv=None,
    which is not a failure (ok=True) -- just not enough edge to profile.

    Per profile point: incoming/outgoing chords over window_px on each
    side (via _chord_scan.chord_pair_at), turn angle = arccos(dot/norms)
    (unsigned, 0 = straight). For a circular arc, the chord from s-w to s
    is exactly parallel to the tangent at the arc's *midpoint* s-w/2 (a
    general property of circles), and likewise the outgoing chord is
    parallel to the tangent at s+w/2 -- so the turn angle is the tangent
    -angle change over an effective arc span of w (from s-w/2 to s+w/2),
    not the full 2w between the two sampled points. kappa is therefore
    turn_rad / (actual_span / 2), using the real searchsorted span (not
    an assumed 2*window_px) so the calibration sweep measures honestly.
    Every valid interior point is included -- unlike kinks.py, there is no
    threshold and no non-max suppression, because the goal here is a
    continuous profile, not discrete flagged events.
    """
    summary = graph_result.summary
    edges: list[EdgeCurvature] = []
    n_scanned = 0

    for path_index in summary.index:
        n_scanned += 1
        coords = skel.path_coordinates(int(path_index)).astype(np.float64)

        if len(coords) < 2:
            edges.append(
                EdgeCurvature(
                    path_index=int(path_index),
                    arc_length_px=0.0,
                    chord_length_px=0.0,
                    tortuosity=None,
                    s_samples=None,
                    curvature_profile_px_inv=None,
                    mean_abs_curvature_px_inv=None,
                    max_abs_curvature_px_inv=None,
                    ok=False,
                    failure_reason="degenerate_edge_fewer_than_2_points",
                )
            )
            continue

        s = arc_length(coords)
        arc_len = float(s[-1])
        chord_len = float(np.linalg.norm(coords[-1] - coords[0]))

        if chord_len < CHORD_LENGTH_EPS_PX:
            tortuosity = None
            failure_reason = "near_zero_chord_length"
        else:
            tortuosity = arc_len / chord_len
            failure_reason = None

        s_samples = None
        profile = None
        mean_abs = None
        max_abs = None

        if arc_len >= 2 * window_px:
            s_list: list[float] = []
            kappa_list: list[float] = []
            for k in range(1, len(coords) - 1):
                pair = chord_pair_at(coords, s, k, window_px)
                if pair is None:
                    continue
                v_in, v_out = pair
                n_in, n_out = np.linalg.norm(v_in), np.linalg.norm(v_out)
                cos_ang = np.clip(np.dot(v_in, v_out) / (n_in * n_out), -1.0, 1.0)
                turn_rad = float(np.arccos(cos_ang))

                j_back = int(np.searchsorted(s, s[k] - window_px, side="right")) - 1
                j_fwd = int(np.searchsorted(s, s[k] + window_px, side="left"))
                half_span = (s[j_fwd] - s[j_back]) / 2.0
                if half_span < 1e-9:
                    continue

                s_list.append(float(s[k]))
                kappa_list.append(turn_rad / half_span)

            if s_list:
                s_samples = np.array(s_list)
                profile = np.array(kappa_list)
                mean_abs = float(np.mean(np.abs(profile)))
                max_abs = float(np.max(np.abs(profile)))

        edges.append(
            EdgeCurvature(
                path_index=int(path_index),
                arc_length_px=arc_len,
                chord_length_px=chord_len,
                tortuosity=tortuosity,
                s_samples=s_samples,
                curvature_profile_px_inv=profile,
                mean_abs_curvature_px_inv=mean_abs,
                max_abs_curvature_px_inv=max_abs,
                ok=True,
                failure_reason=failure_reason,
            )
        )

    return CurvatureScanResult(edges=edges, n_edges_scanned=n_scanned, window_px=window_px)
