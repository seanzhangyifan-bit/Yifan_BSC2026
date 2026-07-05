"""Network-wide crack orientation anisotropy: is this network rectilinear
/grid-like (strong preferred direction) or mudcrack-like (no preferred
direction)? A geometry measurement, not a chronology one -- independent
of, and does not touch, the junction/poset machinery.

Method: length-weighted axial circular statistics on edge tangent bearings
(the standard "orientation tensor" / fabric-tensor method from structural
geology and fracture-trace analysis). Orientation here is *axial*
(mod 180 deg) -- a segment bearing 10 deg and one bearing 190 deg are the
same crack direction, not opposite vectors -- so bearings are doubled
before averaging (the standard trick that turns an axial quantity into a
vector one Mardia & Jupp's circular-statistics treatment of axial data):
for weighted bearings theta_i with weight w_i,

    C = sum(w_i * cos(2*theta_i)) / sum(w_i)
    S = sum(w_i * sin(2*theta_i)) / sum(w_i)
    A = hypot(C, S)                      in [0, 1]
    dominant_bearing = 0.5 * atan2(S, C)  mod 180 deg

A naive-looking alternative -- building the 2x2 matrix
M = sum(w_i * [[cos(2t),sin(2t)],[sin(2t),-cos(2t)]]) and taking
(lambda1-lambda2)/(lambda1+lambda2) -- is broken: that per-sample matrix
has trace cos(2t)-cos(2t) = 0 identically, so any weighted sum of them is
traceless, its eigenvalues are always (lambda,-lambda), and the ratio is
0/0 even in the perfectly-aligned case. The fix used here is the standard
one: T = (I+M)/2 has eigenvalues (1+A)/2 and (1-A)/2 with A = hypot(C,S)
exactly the mean resultant length of the doubled bearings -- reported
directly rather than through an eigendecomposition, since it is already
closed-form.

[cited] This is not a novel method: length-weighted axial circular
statistics and the doubled-angle construction are standard directional
-statistics technique (Mardia & Jupp, "Directional Statistics", Wiley,
2000; also Fisher, "Statistical Analysis of Circular Data", Cambridge
University Press, 1993, which is the reference more commonly used in
earth-science fracture/joint-orientation work). The specific "2nd-order
orientation tensor with eigenvalues (1+/-A)/2" framing is the same
formalism as Advani & Tucker, "The Use of Tensors to Describe and Predict
Fiber Orientation in Short Fiber Composites", Journal of Rheology, 1987 --
the standard reference wherever an "orientation tensor" is used for fiber
or line-like feature orientation. What is *not* drawn from a specific
paper is the scan that turns this project's skeletonized pixel polylines
into bearing samples in the first place (window size, one sample per
interior pixel, arc-length weighting, near-junction exclusion) -- that is
this project's own adaptation of the general method to this data
structure, not itself a cited technique.

Known blind spot, not a bug: this is a *2nd-order* fabric tensor, and an
equal-weight orthogonal bimodal distribution (e.g. 50% of length at 0 deg,
50% at 90 deg -- an idealized rectilinear grid) gives C=S=0 exactly, i.e.
A=0, indistinguishable from true isotropy. A 2nd-order tensor simply
cannot see 180-deg-periodic structure in the doubled-angle distribution
(here, 90 deg apart in raw bearing space folds to exactly opposite points
after doubling, which cancel). [cited] This is a known limitation of the
2nd-order tensor, not particular to this implementation -- it is the same
reason Advani & Tucker (1987) also define a 4th-order orientation tensor
where a 2nd-order description is insufficient; the histogram is used here
as the cheaper fix instead of a 4th-order tensor. The raw orientation histogram
(histogram_weighted_counts) is therefore a *required* companion output,
not decoration -- it is the only thing here that can tell "two peaks 90
deg apart" apart from "flat" (see test_anisotropy.py's documented grid
case). Report A as [measured]; any "grid-like"/"mudcrack-like" verbal
classification built on it is [interpreted] and must be read alongside
the histogram, per CLAUDE.md's evidence-level discipline.
"""

from dataclasses import dataclass

import numpy as np
import skan

from ._chord_scan import arc_length, chord_pair_at
from .graph import GraphResult

ORIENT_WINDOW_PX_PLACEHOLDER = 10.0
# [PLACEHOLDER] chord window (arc length) on each side of each scan point,
# used to get a smoothed tangent bearing (see compute_orientation_samples).
# Same jitter-averaging scale reasoning as curvature.py/kinks.py; not
# derived from calibrated h/um-per-px (none exists yet).

ROSE_HISTOGRAM_N_BINS = 18  # display resolution only, not a fitted parameter

_BEARING_EPS = 1e-9


def _bearing_deg(vec: np.ndarray) -> float:
    """0 deg = +col, 90 deg = -row (CCW in array space) -- same convention
    as junctions.py's/corners.py's _bearing_deg and synthetic.py's
    _draw_rotated_arm. Not folded mod 180 here; callers fold as needed."""
    return float(np.degrees(np.arctan2(-vec[0], vec[1])))


@dataclass
class OrientationSample:
    path_index: int
    s_mid: float  # [measured] arc-length position along the edge
    bearing_deg: float  # [measured] axial, folded to [0, 180)
    weight_px: float  # [measured] local arc-length weight


@dataclass
class AnisotropyResult:
    anisotropy_index: float  # A = hypot(C, S) in [0, 1] [measured]
    dominant_bearing_deg: float  # [measured]; meaningless when anisotropy_index is small
    eigenvalues: tuple[float, float]  # of T = (I+M)/2: ((1+A)/2, (1-A)/2) [measured]
    total_weighted_length_px: float  # [measured]
    n_samples: int  # [measured]
    histogram_bin_edges_deg: np.ndarray  # [0, 180], required companion output -- not decoration
    histogram_weighted_counts: np.ndarray  # [measured]
    window_px: float  # [PLACEHOLDER]


def anisotropy_index_from_bearings(
    bearings_deg: np.ndarray, weights: np.ndarray | None = None
) -> tuple[float, float]:
    """Pure function: (anisotropy_index, dominant_bearing_deg) from axial
    bearings (mod 180 deg; folded here so callers need not pre-fold) and
    optional weights (equal weight if None). Single implementation of the
    corrected math above -- used both by compute_anisotropy() on real
    skeleton samples and directly by tests for closed-form/Monte-Carlo
    ground truth, so the math is verified once, not twice.
    """
    bearings = np.asarray(bearings_deg, dtype=np.float64)
    w = np.ones_like(bearings) if weights is None else np.asarray(weights, dtype=np.float64)
    total_w = float(w.sum())

    theta2 = np.radians(2.0 * (bearings % 180.0))
    C = float(np.sum(w * np.cos(theta2)) / total_w)
    S = float(np.sum(w * np.sin(theta2)) / total_w)

    anisotropy_index = float(np.hypot(C, S))
    dominant_bearing_deg = float(np.degrees(0.5 * np.arctan2(S, C)) % 180.0)
    return anisotropy_index, dominant_bearing_deg


def compute_orientation_samples(
    skel: skan.Skeleton,
    graph_result: GraphResult,
    *,
    window_px: float = ORIENT_WINDOW_PX_PLACEHOLDER,
) -> list[OrientationSample]:
    """One or more axial-bearing samples per edge, length-weighted.

    For edges with at least 2*window_px of arc length: one sample per
    interior polyline point where a chord pair is available (see
    _chord_scan.chord_pair_at), bearing = direction of the *sum* of the
    two unit chords (a smoothed tangent estimate, not the raw single-pixel
    step direction -- 8-connected skeleton pixels hard-quantize to
    0/45/90/135 deg, and averaging those raw steps directly would inject
    an artificial grid bias into exactly the quantity meant to detect a
    real one). Weight is the local pixel-step spacing (trapezoidal:
    (s[k+1]-s[k-1])/2), so weights approximately sum to the edge's arc
    length minus the two window_px zones nearest each endpoint, where a
    smoothed tangent isn't available -- those zones are exactly where
    junction-blob skeleton jitter is worst anyway (junctions.py excludes
    the same region for the same reason), so excluding them from the
    orientation stat is a feature, not a gap.

    Edges shorter than 2*window_px fall back to a single endpoint-to
    -endpoint chord sample (weight = full arc length) -- unlike kink
    -flagging, orientation needs every edge's contribution, not just long
    ones, so short edges are not simply dropped.

    A sample is skipped only when no stable direction exists at all (a
    zero-length chord, or an exact 180-deg reversal where the two unit
    chords cancel) -- both are surfacing "no signal here", not guessing.
    """
    summary = graph_result.summary
    samples: list[OrientationSample] = []

    for path_index in summary.index:
        coords = skel.path_coordinates(int(path_index)).astype(np.float64)
        if len(coords) < 2:
            continue

        s = arc_length(coords)
        arc_len = float(s[-1])

        if arc_len < 2 * window_px:
            v = coords[-1] - coords[0]
            if np.linalg.norm(v) < _BEARING_EPS:
                continue
            bearing = _bearing_deg(v) % 180.0
            samples.append(
                OrientationSample(
                    path_index=int(path_index),
                    s_mid=arc_len / 2.0,
                    bearing_deg=bearing,
                    weight_px=arc_len,
                )
            )
            continue

        for k in range(1, len(coords) - 1):
            pair = chord_pair_at(coords, s, k, window_px)
            if pair is None:
                continue
            v_in, v_out = pair
            u_in = v_in / np.linalg.norm(v_in)
            u_out = v_out / np.linalg.norm(v_out)
            direction = u_in + u_out
            n_dir = np.linalg.norm(direction)
            if n_dir < _BEARING_EPS:
                continue  # near-180 reversal/cusp: no stable tangent here

            bearing = _bearing_deg(direction) % 180.0
            weight = (s[k + 1] - s[k - 1]) / 2.0
            samples.append(
                OrientationSample(
                    path_index=int(path_index),
                    s_mid=float(s[k]),
                    bearing_deg=bearing,
                    weight_px=weight,
                )
            )

    return samples


def compute_anisotropy(
    skel: skan.Skeleton,
    graph_result: GraphResult,
    *,
    window_px: float = ORIENT_WINDOW_PX_PLACEHOLDER,
    n_hist_bins: int = ROSE_HISTOGRAM_N_BINS,
) -> AnisotropyResult:
    """Network-wide anisotropy index, dominant bearing, and rose histogram
    from all edges' orientation samples (see compute_orientation_samples).
    """
    samples = compute_orientation_samples(skel, graph_result, window_px=window_px)
    bin_edges = np.linspace(0.0, 180.0, n_hist_bins + 1)

    if not samples:
        # No orientation data at all (e.g. an empty graph). Report the
        # isotropic default (A=0) explicitly rather than fabricate a
        # direction -- n_samples=0 flags that this is absence of data, not
        # a measured isotropic network.
        return AnisotropyResult(
            anisotropy_index=0.0,
            dominant_bearing_deg=0.0,
            eigenvalues=(0.5, 0.5),
            total_weighted_length_px=0.0,
            n_samples=0,
            histogram_bin_edges_deg=bin_edges,
            histogram_weighted_counts=np.zeros(n_hist_bins),
            window_px=window_px,
        )

    bearings = np.array([sample.bearing_deg for sample in samples])
    weights = np.array([sample.weight_px for sample in samples])

    anisotropy_index, dominant_bearing_deg = anisotropy_index_from_bearings(bearings, weights)
    eigenvalues = ((1.0 + anisotropy_index) / 2.0, (1.0 - anisotropy_index) / 2.0)
    counts, _ = np.histogram(bearings, bins=bin_edges, weights=weights)

    return AnisotropyResult(
        anisotropy_index=anisotropy_index,
        dominant_bearing_deg=dominant_bearing_deg,
        eigenvalues=eigenvalues,
        total_weighted_length_px=float(weights.sum()),
        n_samples=len(samples),
        histogram_bin_edges_deg=bin_edges,
        histogram_weighted_counts=counts,
        window_px=window_px,
    )
