"""Stage 4: classify degree-3 junctions as T / Y / ambiguous via an annulus
angle measurement around each vertex.

Only degree-3 nodes are classified. Degree>=4 junctions are counted (see
GraphResult.n_junctions_deg_ge4) but never decomposed pairwise here -- the
annulus method assumes a clean 3-way star; CLAUDE.md is explicit that
higher-valence junctions get no invented geometry.

This module produces plain per-junction records only. It does not assemble
a precedence graph -- that is stage 5's job, later.

Why an annulus, not the whole edge or the exact vertex: real crack edges are
curved, so "the angle at the junction" is only meaningful as a *local*
quantity. Averaging direction over an edge's full length would measure
wherever the crack happened to curve to, not the direction at the junction.
Conversely, using pixels right at the vertex (radius ~ 0) hits the worst
skeletonization jitter, since thinning algorithms are least stable exactly
at branch points. The annulus band (inner_radius_px to outer_radius_px) is
the compromise: far enough out to skip the jitter, close enough in to still
reflect the junction's local approach direction rather than the edge's
downstream curvature.

Why a tangent fit, not a chord: reducing an arm to the chord from the
vertex to the band centroid is biased whenever the arm is curved -- the
chord rotates toward the center of curvature by roughly half the arc angle
the band subtends. On a curved host crack, both host-arm chords rotate the
same way, so a genuine through-crack reads as ~145-160 deg instead of
~180 deg and a true T-junction gets misfiled as "ambiguous" (observed on
real micrographs). The tangent direction *at* the vertex has no such bias:
it is continuous through a smooth crack regardless of curvature. So each
arm's band pixels are fitted as row(s), col(s) quadratics in arc length s
(s = 0 at the vertex) and the direction is the fitted derivative at s = 0,
which removes the chord bias to first order. Because that derivative is
extrapolated back from the band, its noise sensitivity is governed by the
band length: over a short window (~20 px), +/-1 px skeleton wobble swings
the tangent by 10-25 deg, so the default window is long (~60 px, see
ANNULUS_OUTER_PX_PLACEHOLDER) and short bands degrade to a line fit rather
than an unstable quadratic (see fit_degree). The fit is not anchored at
the vertex pixel -- that pixel sits inside the junction blob and is
systematically displaced, so anchoring biases the direction (verified).
The quadratic's second derivative also yields the signed curvature at the
vertex for free -- groundwork for CLAUDE.md's second chronometer (approach
curvature).

Curvature sign convention: kappa = (r'c'' - c'r'') / (r'^2 + c'^2)^(3/2)
with derivatives taken along travel *away from the vertex*, in (row, col)
coordinates. The sign therefore flips with travel direction: a smooth
through-going host shows equal-magnitude, *opposite-signed* curvature on
its two arms (they are the same curve traversed in opposite directions),
while the magnitudes match 1/R for a circular arc of radius R.

Bearings and sector gaps, not pairwise arccos angles: an earlier version of
this module reported the three *unsigned pairwise* angles between the arm
direction vectors (arccos of the dot product, each in [0, 180]). Those do
NOT sum to 360 in general -- arccos folds any reflex sector back onto
[0, 180], silently discarding the fact that it was reflex (verified on
real data: a junction with true sector gaps {83.5, 74.2, 202.3} reported
as pairwise angles {83.5, 74.2, 157.7}, summing to 315, not 360). This
is confusing and hides a real geometric fact (one side of this junction
is reflex, not acute). The fix: give each arm a signed **bearing**
(_bearing_deg, atan2-based, range (-180, 180]), sort the three bearings
around the full circle, and take the three consecutive gaps (wrapping) --
these sum to exactly 360 by construction and never lose the reflex/acute
distinction. Classification is now phrased in terms of these gaps
(classify_from_gaps): a T is two ~90 deg gaps plus one ~180 deg gap (the
empty side between the two host arms); a Y is three ~120 deg gaps.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
import skan

from .graph import GraphResult

ANNULUS_INNER_PX_PLACEHOLDER = 5.0  # 🔴 assumed — see CALIBRATION.md

ANNULUS_OUTER_PX_PLACEHOLDER = 60.0  # 🟡 empirical, uncalibrated — see CALIBRATION.md

QUAD_MIN_SPAN_PX = 15.0  # 🔴 assumed — see CALIBRATION.md

Y_ANGLE_TOL_DEG_PLACEHOLDER = 15.0  # 🔴 assumed — see CALIBRATION.md

T_STRAIGHT_TOL_DEG_PLACEHOLDER = 20.0  # 🔴 assumed — see CALIBRATION.md

T_RIGHT_TOL_DEG_PLACEHOLDER = 20.0  # 🔴 assumed — see CALIBRATION.md


@dataclass
class EdgeDirection:
    path_index: int
    direction: np.ndarray | None  # unit (drow, dcol) tangent at the vertex, [measured]
    bearing_deg: float | None  # [measured] signed, see _bearing_deg() for convention
    curvature_per_px: float | None  # signed, [measured]; None unless fit_degree == 2
    fit_degree: int  # [measured] 2 = quadratic fit, 1 = line fit, 0 = chord fallback
    fit_rms_px: float | None  # [measured] RMS residual of the fit over the band; None for chord (fit_degree=0)
    fit_coef_row: np.ndarray | None  # np.polyfit coefficients for row(s); None for chord (fit_degree=0)
    fit_coef_col: np.ndarray | None  # np.polyfit coefficients for col(s); None for chord (fit_degree=0)
    band_s_range: tuple[float, float] | None  # (s_min, s_max) actually fitted; None for chord
    n_points_in_band: int  # [measured]
    annulus_clipped: bool  # [measured] True if edge's far end is inside outer radius
    effective_inner_radius_px: float  # [measured] max(inner_radius_px, vertex_halfwidth_px) actually used
    ok: bool
    failure_reason: str | None


@dataclass
class JunctionClassification:
    node_id: int
    coord: tuple[float, float]  # (row, col) [measured]
    vertex_halfwidth_px: float | None  # [measured] local crack half-width at the vertex (EDT); None if not supplied
    edge_directions: list[EdgeDirection]  # len 3 (or fewer if malformed) [measured]
    sector_gaps_deg: list[float] | None  # 3 values, sum to 360 exactly [measured]; None if any edge failed
    label: str  # "T" | "Y" | "ambiguous" | "insufficient_data"  [interpreted]
    abutter_path_index: int | None  # [interpreted], set only when label == "T"
    host_path_indices: tuple[int, int] | None  # [interpreted], the two collinear arms
    failure_reason: str | None  # populated when label == "insufficient_data"


@dataclass
class JunctionAnalysisResult:
    classifications: list[JunctionClassification]  # one entry per degree-3 node
    n_deg3_total: int
    n_t: int
    n_y: int
    n_ambiguous: int
    n_insufficient_data: int
    n_deg_ge4_unclassified: int  # carried through from GraphResult, report-only
    inner_radius_px: float  # [PLACEHOLDER]
    outer_radius_px: float  # [PLACEHOLDER]
    y_angle_tol_deg: float  # [PLACEHOLDER]
    t_straight_tol_deg: float  # [PLACEHOLDER]
    t_right_tol_deg: float  # [PLACEHOLDER]


def _build_incidence_index(summary: pd.DataFrame) -> dict[int, list[tuple[int, bool]]]:
    """node_id -> list of (path_index, node_is_src).

    A self-loop row (src==dst) appears twice for its node, once with each
    boolean -- correct, since it attaches to that node on both ends.
    """
    index: dict[int, list[tuple[int, bool]]] = {}
    for row_idx, src, dst in zip(
        summary.index, summary["node_id_src"], summary["node_id_dst"]
    ):
        index.setdefault(int(src), []).append((row_idx, True))
        index.setdefault(int(dst), []).append((row_idx, False))
    return index


def _edge_direction(
    skel: skan.Skeleton,
    path_index: int,
    node_is_src: bool,
    inner_radius_px: float,
    outer_radius_px: float,
) -> EdgeDirection:
    coords = skel.path_coordinates(path_index).astype(np.float64)  # (row, col), src->dst
    if not node_is_src:
        coords = coords[::-1]
    vertex = coords[0]  # exact vertex coordinate
    d = np.linalg.norm(coords - vertex, axis=1)
    band_mask = (d >= inner_radius_px) & (d <= outer_radius_px)
    n_in_band = int(band_mask.sum())
    max_d = float(d.max())
    annulus_clipped = max_d < outer_radius_px

    if n_in_band == 0:
        reason = (
            "edge_shorter_than_inner_radius"
            if max_d < inner_radius_px
            else "no_points_between_inner_and_outer_radius"
        )
        return EdgeDirection(
            path_index=path_index,
            direction=None,
            bearing_deg=None,
            curvature_per_px=None,
            fit_degree=0,
            fit_rms_px=None,
            fit_coef_row=None,
            fit_coef_col=None,
            band_s_range=None,
            n_points_in_band=0,
            annulus_clipped=annulus_clipped,
            effective_inner_radius_px=inner_radius_px,
            ok=False,
            failure_reason=reason,
        )

    # Arc length s from the vertex along the polyline; the fit is in s so
    # the derivative at s=0 is the tangent *at the vertex*, extrapolated
    # back from the band (the band itself still excludes the jittery
    # pixels closest to the vertex -- see module docstring).
    steps = np.linalg.norm(np.diff(coords, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(steps)])
    s_band = s[band_mask]
    band = coords[band_mask]

    # The fit is deliberately NOT anchored at the vertex: the vertex pixel
    # sits inside the junction blob where thick strokes merge, so it is
    # systematically displaced from the arm's centerline -- anchoring there
    # biases every arm direction (verified: it degrades both synthetic and
    # real-image results). Stability against pixel wobble comes from the
    # window length instead (see ANNULUS_OUTER_PX_PLACEHOLDER).
    curvature = None
    fit_rms = None
    fit_coef_row = None
    fit_coef_col = None
    band_s_range = (float(s_band.min()), float(s_band.max()))
    span = float(s_band.max() - s_band.min())
    if n_in_band >= 6 and span >= QUAD_MIN_SPAN_PX:
        # Quadratic fit: tangent at s=0 unbiased by curvature to first
        # order, signed curvature as a by-product (see docstring for the
        # sign convention).
        poly_r = np.polyfit(s_band, band[:, 0], 2)
        poly_c = np.polyfit(s_band, band[:, 1], 2)
        r1, c1 = poly_r[1], poly_c[1]
        r2, c2 = 2.0 * poly_r[0], 2.0 * poly_c[0]
        vec = np.array([r1, c1])
        speed_sq = r1 * r1 + c1 * c1
        if speed_sq > 1e-12:
            curvature = float((r1 * c2 - c1 * r2) / speed_sq**1.5)
        resid_r = band[:, 0] - np.polyval(poly_r, s_band)
        resid_c = band[:, 1] - np.polyval(poly_c, s_band)
        fit_rms = float(np.sqrt(np.mean(resid_r**2 + resid_c**2)))
        fit_coef_row, fit_coef_col = poly_r, poly_c
        fit_degree = 2
    elif n_in_band >= 2:
        # Band too short for a stable curvature term: line fit (direction =
        # average tangent over the band; no curvature estimate).
        poly_r = np.polyfit(s_band, band[:, 0], 1)
        poly_c = np.polyfit(s_band, band[:, 1], 1)
        vec = np.array([poly_r[0], poly_c[0]])
        resid_r = band[:, 0] - np.polyval(poly_r, s_band)
        resid_c = band[:, 1] - np.polyval(poly_c, s_band)
        fit_rms = float(np.sqrt(np.mean(resid_r**2 + resid_c**2)))
        fit_coef_row, fit_coef_col = poly_r, poly_c
        fit_degree = 1
    else:
        # Single point: chord from the vertex. No fit, so no residual and
        # nothing to draw as a fitted curve.
        vec = band.mean(axis=0) - vertex
        fit_degree = 0
        band_s_range = None

    norm = np.linalg.norm(vec)
    if norm < 1e-9:
        return EdgeDirection(
            path_index=path_index,
            direction=None,
            bearing_deg=None,
            curvature_per_px=None,
            fit_degree=fit_degree,
            fit_rms_px=fit_rms,
            fit_coef_row=fit_coef_row,
            fit_coef_col=fit_coef_col,
            band_s_range=band_s_range,
            n_points_in_band=n_in_band,
            annulus_clipped=annulus_clipped,
            effective_inner_radius_px=inner_radius_px,
            ok=False,
            failure_reason="degenerate_zero_length_direction",
        )

    unit = vec / norm
    return EdgeDirection(
        path_index=path_index,
        direction=unit,
        bearing_deg=_bearing_deg(unit),
        curvature_per_px=curvature,
        fit_degree=fit_degree,
        fit_rms_px=fit_rms,
        fit_coef_row=fit_coef_row,
        fit_coef_col=fit_coef_col,
        band_s_range=band_s_range,
        n_points_in_band=n_in_band,
        annulus_clipped=annulus_clipped,
        effective_inner_radius_px=inner_radius_px,
        ok=True,
        failure_reason=None,
    )


def _bearing_deg(unit_vec: np.ndarray) -> float:
    """Signed bearing of a unit (drow, dcol) vector, range (-180, 180].

    Convention: 0 deg = +col ("east"), 90 deg = -row ("up" in image
    display, i.e. counterclockwise in array-index space) -- matches the
    bearing_deg convention already used in synthetic.py's _draw_rotated_arm.
    """
    return float(np.degrees(np.arctan2(-unit_vec[0], unit_vec[1])))


def sector_gaps_deg_from_bearings(bearings: list[float]) -> list[tuple[int, int, float]]:
    """Three signed bearings -> the three consecutive sector gaps going
    around the circle, wrapping. Each returned tuple is
    (from_local_index, to_local_index, gap_deg); the three gap_deg values
    always sum to exactly 360 (up to floating point), unlike unsigned
    pairwise angles (arccos), which fold any reflex gap back into [0,180]
    and can under-report by up to 180 deg on a reflex junction.

    Public (no leading underscore): shared with corners.py's independent
    background-tile-wall cross-check, so both measurement methods are
    classified by the identical rule -- any T/Y/ambiguous disagreement
    between them is then guaranteed to come from the input bearings, not
    from two subtly different classification implementations.
    """
    order = sorted(range(3), key=lambda i: bearings[i] % 360.0)
    b = [bearings[i] % 360.0 for i in order]
    return [
        (order[0], order[1], b[1] - b[0]),
        (order[1], order[2], b[2] - b[1]),
        (order[2], order[0], 360.0 - b[2] + b[0]),
    ]


def classify_from_gaps(
    gaps: list[tuple[int, int, float]],
    y_tol: float,
    t_straight_tol: float,
    t_right_tol: float,
) -> tuple[str, int | None, tuple[int, int] | None]:
    """Public (no leading underscore): shared with corners.py, see
    sector_gaps_deg_from_bearings' docstring for why."""
    gap_values = [g for _, _, g in gaps]

    # Y: all three sector gaps near 120 deg. Checked first so that if
    # tolerances are ever loosened enough to overlap the T template, Y wins
    # deterministically rather than the outcome depending on list order.
    if all(abs(g - 120.0) <= y_tol for g in gap_values):
        return "Y", None, None

    # T: the largest gap is the empty side between the two host arms (they
    # bound it); the remaining arm is the abutter, and the two gaps on
    # either side of it (abutter-to-each-host-arm) must both be near 90 deg.
    i, j, g_max = max(gaps, key=lambda t: t[2])
    if abs(g_max - 180.0) <= t_straight_tol:
        k = ({0, 1, 2} - {i, j}).pop()
        g_ik = next(g for (p, q, g) in gaps if {p, q} == {i, k})
        g_jk = next(g for (p, q, g) in gaps if {p, q} == {j, k})
        if abs(g_ik - 90.0) <= t_right_tol and abs(g_jk - 90.0) <= t_right_tol:
            return "T", k, (i, j)

    return "ambiguous", None, None


def classify_junctions(
    skel: skan.Skeleton,
    graph_result: GraphResult,
    *,
    inner_radius_px: float = ANNULUS_INNER_PX_PLACEHOLDER,
    outer_radius_px: float = ANNULUS_OUTER_PX_PLACEHOLDER,
    y_angle_tol_deg: float = Y_ANGLE_TOL_DEG_PLACEHOLDER,
    t_straight_tol_deg: float = T_STRAIGHT_TOL_DEG_PLACEHOLDER,
    t_right_tol_deg: float = T_RIGHT_TOL_DEG_PLACEHOLDER,
    medial_radius: np.ndarray | None = None,
) -> JunctionAnalysisResult:
    """Classify every degree-3 junction node as T / Y / ambiguous.

    Every degree-3 node gets exactly one JunctionClassification record --
    if its geometry can't be measured (too short an edge, missing data),
    it gets label="insufficient_data" with a failure_reason, never silently
    dropped, per CLAUDE.md's "surface the gap, don't fill it" discipline.

    `medial_radius`, if supplied (see skeleton.py's SkeletonResult), is the
    distance-transform half-width at every mask pixel. At each vertex, the
    fit band's *effective* inner radius is max(inner_radius_px,
    vertex_halfwidth_px): where three thick strokes merge, the junction
    blob itself can be wider than the inner_radius_px placeholder, and
    fitting inside it would use pixels that are still part of the merge
    artifact, not the arm's own centerline. Without medial_radius, this
    falls back to plain inner_radius_px (unchanged prior behavior).
    """
    if inner_radius_px >= outer_radius_px:
        raise ValueError("annulus inner radius must be < outer radius")

    summary = graph_result.summary
    incidence = _build_incidence_index(summary)
    classifications: list[JunctionClassification] = []

    for node_id, degree, coord in zip(
        graph_result.node_ids, graph_result.node_degree, graph_result.node_coords
    ):
        if degree != 3:
            continue

        node_id = int(node_id)
        coord_f = (float(coord[0]), float(coord[1]))

        vertex_halfwidth = None
        effective_inner = inner_radius_px
        if medial_radius is not None:
            r_idx = int(round(coord[0]))
            c_idx = int(round(coord[1]))
            vertex_halfwidth = float(medial_radius[r_idx, c_idx])
            effective_inner = max(inner_radius_px, vertex_halfwidth)

        arms = incidence.get(node_id, [])
        if len(arms) != 3:
            classifications.append(
                JunctionClassification(
                    node_id,
                    coord_f,
                    vertex_halfwidth,
                    [],
                    None,
                    "insufficient_data",
                    None,
                    None,
                    f"expected 3 incident arms, found {len(arms)}",
                )
            )
            continue

        edge_dirs = [
            _edge_direction(skel, path_idx, is_src, effective_inner, outer_radius_px)
            for path_idx, is_src in arms
        ]
        if not all(ed.ok for ed in edge_dirs):
            reasons = "; ".join(ed.failure_reason for ed in edge_dirs if not ed.ok)
            classifications.append(
                JunctionClassification(
                    node_id,
                    coord_f,
                    vertex_halfwidth,
                    edge_dirs,
                    None,
                    "insufficient_data",
                    None,
                    None,
                    reasons,
                )
            )
            continue

        bearings = [ed.bearing_deg for ed in edge_dirs]
        gaps = sector_gaps_deg_from_bearings(bearings)
        label, abutter_local, host_local = classify_from_gaps(
            gaps, y_angle_tol_deg, t_straight_tol_deg, t_right_tol_deg
        )
        abutter_idx = edge_dirs[abutter_local].path_index if label == "T" else None
        host_idx = (
            (edge_dirs[host_local[0]].path_index, edge_dirs[host_local[1]].path_index)
            if label == "T"
            else None
        )
        classifications.append(
            JunctionClassification(
                node_id,
                coord_f,
                vertex_halfwidth,
                edge_dirs,
                [g for _, _, g in gaps],
                label,
                abutter_idx,
                host_idx,
                None,
            )
        )

    return JunctionAnalysisResult(
        classifications=classifications,
        n_deg3_total=int(graph_result.n_junctions_deg3),
        n_t=sum(c.label == "T" for c in classifications),
        n_y=sum(c.label == "Y" for c in classifications),
        n_ambiguous=sum(c.label == "ambiguous" for c in classifications),
        n_insufficient_data=sum(c.label == "insufficient_data" for c in classifications),
        n_deg_ge4_unclassified=int(graph_result.n_junctions_deg_ge4),
        inner_radius_px=inner_radius_px,
        outer_radius_px=outer_radius_px,
        y_angle_tol_deg=y_angle_tol_deg,
        t_straight_tol_deg=t_straight_tol_deg,
        t_right_tol_deg=t_right_tol_deg,
    )
