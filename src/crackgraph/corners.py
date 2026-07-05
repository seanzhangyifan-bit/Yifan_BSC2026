"""Cross-check stage 4's tangent-fit angle measurement using the geometry
of the *background* (intact-film) tiles between cracks, instead of the
skeleton medial axis.

Motivation: the medial axis is a 1px-wide idealization that gets unstable
exactly where the tangent-fit method needs it most -- at the junction
blob where several thick strokes merge (see junctions.py's docstring for
the history of estimator problems this caused). The background tiles'
walls are the actual crack boundaries; where an abutter crack meets a
host, its finite width visibly notches the host-side tile into two
separate tiles, each with a sharp corner right at the meeting point. That
corner's two wall directions are a direct measurement of the crack
directions there, entirely avoiding the junction blob.

This does NOT make the method immune to curvature bias, though: each wall
direction is still a chord over CORNER_WINDOW_PX, so a severely curved
host wall biases it exactly the way a too-long annulus window biased the
tangent fit (measured directly: scripts/corner_window_sweep.py's
radius=30 px cases show real bias at the window chosen for jitter
robustness). The advantage over the tangent fit is narrower and specific:
no junction-blob/skeleton-jitter problem, not a general cure for
curvature-vs-window tradeoffs.

This is a CROSS-CHECK, not a replacement (decided with the user): CLAUDE.md
already treats independent chronometers (angle, curvature, width) agreeing
or disagreeing as a validation signal that needs no ground truth. This
module adds a fourth, geometrically distinct estimate of the same
per-junction angles and reports where it agrees or disagrees with the
tangent-fit result -- disagreement is logged, not smoothed over.

Two distinct corner geometries are handled, dispatched purely by HOW MANY
corners are found near a junction (checked empirically: at real crack
thicknesses the T notch's corner separation and the Y triple-point's
corner separation are the same order of magnitude, a few px -- spatial
distance between corners is not a reliable way to tell them apart, but
the corner *count* is, since it is fixed by the topology: a T always
notches a tile into exactly 2 pieces, a Y always splits 3 tiles):
- Exactly 2 corners (T-like): each corner has a "host" wall bearing and an
  "abutter" wall bearing; which is which is disambiguated using the
  corner-to-corner direction (the notch runs along the host wall, so it's
  close to parallel/antiparallel to each corner's host-side bearing).
- Exactly 3 corners (Y-like): each corner's 2 wall bearings are matched
  against the closest bearing from a *different* corner (same absolute
  direction, since both sides of a shared wall point the same way away
  from the shared point).

Any other corner count, or inconsistent pairing (bearings that should
match don't, within tolerance), is left unresolved rather than guessed at.
"""

from dataclasses import dataclass

import numpy as np
from skimage.measure import find_contours

from .junctions import JunctionAnalysisResult, classify_from_gaps, sector_gaps_deg_from_bearings

CORNER_SEARCH_RADIUS_PX = 25.0
# [PLACEHOLDER] how far from a junction vertex to look for background-tile
# corners. Must comfortably exceed typical crack half-width (the T notch's
# corner separation) so both notch corners are found; not yet tied to a
# calibrated h.

CORNER_WINDOW_PX = 10.0
# [PLACEHOLDER] chord half-window (arc length) used to measure each wall's
# direction on either side of a candidate corner point. Chosen from
# scripts/corner_window_sweep.py's measured sweep (straight T's at
# 60/90/120 deg, curved-host T's at radius 30/60 px, jitter 0/0.5/1.0 px),
# scoring each window by worst-case RMSE *and* worst-case unresolved
# fraction together (a small window that "resolves" cleanly on the easy
# cases but fails to find corners at all under jitter is not actually
# better). Summary at window=10: worst-case RMSE 15.6 deg, worst-case
# unresolved 38% (both driven by the jitter=1.0 px cells; jitter=0 cells
# resolve 100% with RMSE well under 5 deg at this window). Re-run the
# script and update this comment if the geometry/jitter grid changes.

CORNER_MIN_TURN_DEG = 45.0
# [PLACEHOLDER] minimum turning angle (see kinks.py's identically-shaped
# scan) to accept a contour point as a real wall corner rather than
# boundary noise. Not calibrated.

ABUTTER_AGREEMENT_TOL_DEG = 30.0
# [PLACEHOLDER] in the T-like (2-corner) case, the two corners' independent
# estimates of the abutter's bearing must agree within this tolerance or
# the pairing is treated as inconsistent (unresolvable) rather than
# silently averaged.

BEARING_MATCH_TOL_DEG = 30.0
# [PLACEHOLDER] in the Y-like (3-corner) case, the greedy bearing-matching
# used to pair up the 6 raw wall bearings into 3 arm bearings requires the
# matched pair to agree within this tolerance; otherwise unresolvable.


@dataclass
class WallCorner:
    contour_index: int
    point_index: int
    coord: tuple[float, float]  # (row, col) [measured]
    wall_bearings_deg: tuple[float, float]  # the two wall directions leaving this corner, [measured]
    turn_deg: float  # [measured]


@dataclass
class CornerCrossCheck:
    node_id: int
    corners: list[WallCorner]  # 0+ corners found near this vertex [measured]
    arm_bearings_deg: list[float] | None  # 3 derived arm bearings, if resolvable [measured]
    sector_gaps_deg: list[float] | None  # via the shared gap function [measured]
    label: str | None  # "T" | "Y" | "ambiguous" | None (unresolvable) [interpreted]
    unresolved_reason: str | None
    agrees_with_tangent_fit: bool | None  # label match, only set when both resolvable [interpreted]
    max_gap_disagreement_deg: float | None  # [measured] largest |corner_gap - tangent_gap| after matching


def find_background_contours(mask_clean: np.ndarray) -> list[np.ndarray]:
    """Contours of the background (intact-film) regions -- the tiles
    between cracks -- as (row, col) polylines. `mask_clean` is the same
    despeckled foreground mask skeletonize_and_prune already computed
    (SkeletonResult.mask_clean), so this reuses stage 2's cleanup rather
    than re-deriving it.
    """
    return find_contours(~mask_clean, 0.5)


def _bearing_deg(vec: np.ndarray) -> float:
    return float(np.degrees(np.arctan2(-vec[0], vec[1])))


def _angle_diff(a: float, b: float) -> float:
    """Smallest signed difference a-b, wrapped to (-180, 180]."""
    return (a - b + 180.0) % 360.0 - 180.0


def _scan_contour_for_corners(
    contour: np.ndarray,
    contour_index: int,
    vertex: np.ndarray,
    search_radius_px: float,
    window_px: float,
    min_turn_deg: float,
) -> list[WallCorner]:
    """Same chord-based turning-angle scan as kinks.py's find_kinks, but
    restricted to points near `vertex` and recording the two wall bearings
    (not just the turn angle) at each kept corner. Contours are treated as
    open arrays with no wraparound at the start/end seam, same
    simplification kinks.py makes for skeleton paths -- a corner exactly at
    a closed contour's arbitrary start/end point would be missed; accepted
    as a rare edge case, not a correctness bug for the general case.
    """
    d_vertex = np.linalg.norm(contour - vertex, axis=1)
    if d_vertex.min() > search_radius_px:
        return []

    steps = np.linalg.norm(np.diff(contour, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(steps)])
    if s[-1] < 2 * window_px:
        return []

    candidates: list[tuple[float, int]] = []
    for k in range(1, len(contour) - 1):
        if d_vertex[k] > search_radius_px:
            continue
        if s[k] < window_px or s[-1] - s[k] < window_px:
            continue
        j_back = int(np.searchsorted(s, s[k] - window_px, side="right")) - 1
        j_fwd = int(np.searchsorted(s, s[k] + window_px, side="left"))
        v_in = contour[k] - contour[j_back]
        v_out = contour[j_fwd] - contour[k]
        n_in, n_out = np.linalg.norm(v_in), np.linalg.norm(v_out)
        if n_in < 1e-9 or n_out < 1e-9:
            continue
        cos_ang = np.clip(np.dot(v_in, v_out) / (n_in * n_out), -1.0, 1.0)
        turn = float(np.degrees(np.arccos(cos_ang)))
        if turn >= min_turn_deg:
            candidates.append((turn, k))

    candidates.sort(reverse=True)
    kept: list[tuple[float, int]] = []
    for turn, k in candidates:
        if all(abs(s[k] - s[k_kept]) >= 2 * window_px for _, k_kept in kept):
            kept.append((turn, k))

    corners = []
    for turn, k in kept:
        j_back = int(np.searchsorted(s, s[k] - window_px, side="right")) - 1
        j_fwd = int(np.searchsorted(s, s[k] + window_px, side="left"))
        # wall bearings, both pointing AWAY from the corner along their wall
        bearing_1 = _bearing_deg(contour[j_back] - contour[k])
        bearing_2 = _bearing_deg(contour[j_fwd] - contour[k])
        corners.append(
            WallCorner(
                contour_index=contour_index,
                point_index=k,
                coord=(float(contour[k][0]), float(contour[k][1])),
                wall_bearings_deg=(bearing_1, bearing_2),
                turn_deg=turn,
            )
        )
    return corners


def _pair_t_like(corners: list[WallCorner]) -> tuple[list[float] | None, str | None]:
    """Exactly 2 spatially-separated corners: disambiguate each corner's
    host vs. abutter bearing using the corner-to-corner direction (the
    notch runs along the host wall, so it's ~parallel/antiparallel to each
    corner's host-side bearing), then combine into 3 arm bearings.
    """
    a, b = corners
    d_ab = np.array(b.coord) - np.array(a.coord)
    if np.linalg.norm(d_ab) < 1e-6:
        return None, "corners_coincide_but_treated_as_separated"
    bearing_ab = _bearing_deg(d_ab)

    def split(corner: WallCorner) -> tuple[float, float]:
        b1, b2 = corner.wall_bearings_deg
        # "host-like" bearing is whichever is closer to bearing_ab mod 180
        # (a wall is a line, not a ray: parallel and antiparallel both count).
        d1 = min(abs(_angle_diff(b1, bearing_ab)), abs(_angle_diff(b1, bearing_ab + 180)))
        d2 = min(abs(_angle_diff(b2, bearing_ab)), abs(_angle_diff(b2, bearing_ab + 180)))
        return (b1, b2) if d1 < d2 else (b2, b1)  # (host_bearing, abutter_bearing)

    host_a, abutter_a = split(a)
    host_b, abutter_b = split(b)

    if abs(_angle_diff(abutter_a, abutter_b)) > ABUTTER_AGREEMENT_TOL_DEG:
        return None, "abutter_bearing_disagreement_between_corners"

    abutter_bearing = (abutter_a + abutter_b) / 2.0  # simple mean; both should agree closely
    return [host_a, host_b, abutter_bearing], None


def _pair_y_like(corners: list[WallCorner]) -> tuple[list[float] | None, str | None]:
    """Exactly 3 co-located corners: each of the 6 raw wall bearings should
    have exactly one close match among bearings from a DIFFERENT corner
    (the shared wall, seen from both adjacent tiles, points the same way).
    Greedy nearest-match; any leftover mismatch beyond tolerance is
    unresolvable rather than force-paired.
    """
    items = [(ci, w) for ci, c in enumerate(corners) for w in c.wall_bearings_deg]
    used = [False] * len(items)
    arm_bearings = []
    for i in range(len(items)):
        if used[i]:
            continue
        ci_i, bearing_i = items[i]
        best_j, best_diff = None, None
        for j in range(i + 1, len(items)):
            if used[j]:
                continue
            ci_j, bearing_j = items[j]
            if ci_j == ci_i:
                continue  # never match a corner's own two bearings together
            diff = abs(_angle_diff(bearing_i, bearing_j))
            if best_diff is None or diff < best_diff:
                best_diff, best_j = diff, j
        if best_j is None or best_diff > BEARING_MATCH_TOL_DEG:
            return None, "y_bearing_matching_inconsistent"
        used[i] = True
        used[best_j] = True
        arm_bearings.append((bearing_i + items[best_j][1]) / 2.0)

    if len(arm_bearings) != 3:
        return None, "y_bearing_matching_wrong_count"
    return arm_bearings, None


def _resolve_arm_bearings(corners: list[WallCorner]) -> tuple[list[float] | None, str | None]:
    """Dispatch purely by corner count (see module docstring for why
    spatial separation isn't a reliable T-vs-Y discriminator). A
    genuinely-wrong count (e.g. a spurious 3rd corner near a real T) is
    still caught downstream: _pair_y_like's bearing-matching consistency
    check fails on bearings that don't actually pair up, returning
    unresolved rather than a wrong label.
    """
    if len(corners) == 2:
        return _pair_t_like(corners)
    if len(corners) == 3:
        return _pair_y_like(corners)
    return None, f"unsupported_corner_count_{len(corners)}"


def cross_check_junctions(
    junction_result: JunctionAnalysisResult,
    contours: list[np.ndarray],
    *,
    search_radius_px: float = CORNER_SEARCH_RADIUS_PX,
    window_px: float = CORNER_WINDOW_PX,
    min_turn_deg: float = CORNER_MIN_TURN_DEG,
    y_angle_tol_deg: float,
    t_straight_tol_deg: float,
    t_right_tol_deg: float,
) -> list[CornerCrossCheck]:
    """One CornerCrossCheck per degree-3 junction (every label, including
    ambiguous/insufficient_data from the tangent-fit method -- the corner
    geometry is independent and might resolve or independently confirm
    those too, per CLAUDE.md's "log disagreements, don't smooth them over").
    Uses the SAME classify_from_gaps as junctions.py so a T/Y/ambiguous
    disagreement can only come from the input bearings, not from two
    different classification rules.
    """
    results = []
    for jc in junction_result.classifications:
        vertex = np.array(jc.coord)
        corners: list[WallCorner] = []
        for ci, contour in enumerate(contours):
            corners.extend(
                _scan_contour_for_corners(contour, ci, vertex, search_radius_px, window_px, min_turn_deg)
            )

        arm_bearings, unresolved_reason = _resolve_arm_bearings(corners)
        gaps = None
        label = None
        if arm_bearings is not None:
            gap_tuples = sector_gaps_deg_from_bearings(arm_bearings)
            gaps = [g for _, _, g in gap_tuples]
            label, _, _ = classify_from_gaps(gap_tuples, y_angle_tol_deg, t_straight_tol_deg, t_right_tol_deg)

        agrees = None
        max_disagreement = None
        if label is not None and jc.sector_gaps_deg is not None:
            agrees = label == jc.label
            corner_sorted = sorted(gaps)
            tangent_sorted = sorted(jc.sector_gaps_deg)
            max_disagreement = max(abs(a - b) for a, b in zip(corner_sorted, tangent_sorted))

        results.append(
            CornerCrossCheck(
                node_id=jc.node_id,
                corners=corners,
                arm_bearings_deg=arm_bearings,
                sector_gaps_deg=gaps,
                label=label,
                unresolved_reason=unresolved_reason,
                agrees_with_tangent_fit=agrees,
                max_gap_disagreement_deg=max_disagreement,
            )
        )
    return results
