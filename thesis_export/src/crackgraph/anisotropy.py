"""Crack orientation: the length-weighted distribution of crack directions,
drawn as a rose plot.

Directions are axial (mod 180°): a segment at 10° and one at 190° are the
same crack direction. Each segment is sampled along its length with a
smoothed tangent (compute_orientation_samples), weighted by arc length, and
binned into an 18-bin histogram over 0–180° (anisotropy_from_samples).

The histogram is reported as is, not reduced to one index: a single
2nd-order index reads an equal-weight orthogonal grid as having no
preferred direction, the same as random directions. Only the histogram
shows the two peaks. Axial statistics: Mardia & Jupp, "Directional
Statistics", 2000; Fisher, "Statistical Analysis of Circular Data", 1993.
"""

from dataclasses import dataclass

import numpy as np
import skan

from ._chord_scan import arc_length, chord_pair_at
from .graph import GraphResult

ORIENT_WINDOW_PX_PLACEHOLDER = 10.0
# [PLACEHOLDER] chord window (arc length) on each side of each scan point,
# used to get a smoothed tangent bearing (see compute_orientation_samples).
# Same jitter-averaging scale reasoning as curvature.py; not derived from
# calibrated h/um-per-px (none exists yet).

ROSE_HISTOGRAM_N_BINS = 18  # display resolution only, not a fitted parameter

_BEARING_EPS = 1e-9


def _bearing_deg(vec: np.ndarray) -> float:
    """0 deg = +col, 90 deg = -row (CCW in array space) -- same convention
    as synthetic.py's _draw_rotated_arm. Not folded mod 180 here; callers fold as needed."""
    return float(np.degrees(np.arctan2(-vec[0], vec[1])))


@dataclass
class OrientationSample:
    path_index: int
    s_mid: float  # [measured] arc-length position along the edge
    bearing_deg: float  # [measured] axial, folded to [0, 180)
    weight_px: float  # [measured] local arc-length weight
    row: float = float("nan")  # image position of the sample, for assigning it to a region
    col: float = float("nan")


@dataclass
class AnisotropyResult:
    total_weighted_length_px: float  # [measured]
    n_samples: int  # [measured]
    histogram_bin_edges_deg: np.ndarray  # [0, 180]
    histogram_weighted_counts: np.ndarray  # [measured]
    window_px: float  # [PLACEHOLDER]


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
    junction-blob skeleton jitter is worst anyway, so excluding them from the
    orientation stat is a feature, not a gap.

    Edges shorter than 2*window_px fall back to a single endpoint-to
    -endpoint chord sample (weight = full arc length) -- unlike a
    threshold-based corner flag, orientation needs every edge's
    contribution, not just long ones, so short edges are not simply
    dropped.

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
                    row=float(coords[len(coords) // 2, 0]),
                    col=float(coords[len(coords) // 2, 1]),
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
                    row=float(coords[k, 0]),
                    col=float(coords[k, 1]),
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
    """Rose histogram from every edge's orientation samples (see
    compute_orientation_samples)."""
    samples = compute_orientation_samples(skel, graph_result, window_px=window_px)
    return anisotropy_from_samples(samples, window_px=window_px, n_hist_bins=n_hist_bins)


def anisotropy_from_samples(
    samples: list[OrientationSample],
    *,
    window_px: float = ORIENT_WINDOW_PX_PLACEHOLDER,
    n_hist_bins: int = ROSE_HISTOGRAM_N_BINS,
) -> AnisotropyResult:
    """Rose histogram (length-weighted, 0-180 deg) from a set of orientation
    samples -- all of an image's, or only one region's."""
    bin_edges = np.linspace(0.0, 180.0, n_hist_bins + 1)

    if not samples:
        # No orientation data (e.g. an empty graph): an empty histogram,
        # flagged by n_samples=0.
        return AnisotropyResult(
            total_weighted_length_px=0.0,
            n_samples=0,
            histogram_bin_edges_deg=bin_edges,
            histogram_weighted_counts=np.zeros(n_hist_bins),
            window_px=window_px,
        )

    bearings = np.array([sample.bearing_deg for sample in samples])
    weights = np.array([sample.weight_px for sample in samples])

    counts, _ = np.histogram(bearings, bins=bin_edges, weights=weights)

    return AnisotropyResult(
        total_weighted_length_px=float(weights.sum()),
        n_samples=len(samples),
        histogram_bin_edges_deg=bin_edges,
        histogram_weighted_counts=counts,
        window_px=window_px,
    )


def share_near(result: AnisotropyResult, bearing_deg: float, half_width_deg: float = 10.0) -> float:
    """Share of the weighted length in the bins whose centre lies within
    half_width_deg of bearing_deg (axial). With 10° bins and the default,
    that's the two bins touching bearing_deg."""
    edges = result.histogram_bin_edges_deg
    centres = (edges[:-1] + edges[1:]) / 2.0
    d = np.abs(centres - bearing_deg) % 180.0
    d = np.minimum(d, 180.0 - d)
    total = result.histogram_weighted_counts.sum()
    return float(result.histogram_weighted_counts[d < half_width_deg].sum() / total) if total > 0 else 0.0
