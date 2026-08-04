"""Synthetic test image generation: minimal, known-topology/known-angle
junction images.

Used to validate the stage 1-3 chain end-to-end against cases with a known
right answer (exact node/edge counts), and stage 4's annulus angle
measurement against a known ground-truth angle -- rather than just "runs
without crashing" on real data.

Everything above this point is a single isolated junction (one T, one Y,
one bent line). generate_grid/generate_wavy_grid/generate_hexagonal_grid/
generate_grid_with_flakes below instead build small *networks* -- multiple
junctions sharing lines, the way a real percolating crack pattern actually
looks, and the shape crack_stats.xlsx's n_edges/giant_component_fraction/
flaking_excluded_area_pct columns are actually measuring. They exist
because none of the single-junction cases exercise that at all.
"""

import math

import numpy as np
from skimage.draw import disk, polygon


def _smooth_jitter_1d(
    t_values: np.ndarray,
    jitter_px: float,
    rng: np.random.Generator,
    control_spacing_px: float = 8.0,
) -> np.ndarray:
    """Spatially-correlated lateral noise, sampled at `t_values` (arc
    length or column position), anchored to 0 at t=0.

    Independent per-pixel noise (tried first) rasterizes into a jagged
    boundary that skeletonizes into dozens of spurious spur branches per
    arm -- confirmed empirically (see scripts/window_sweep.py's git
    history / dev notes: an early version of this jitter model produced
    40-170 "junctions" per single-junction test image at jitter_px=0.5-1.0,
    i.e. it was testing topology breakage, not angle-estimation noise).
    Real skeletonization wobble is smooth/low-frequency, not per-pixel
    white noise, so this instead perturbs a coarse grid of control points
    (spaced `control_spacing_px` apart) and linearly interpolates -- a
    simple, reproducible way to get smooth wobble without claiming it
    matches any specific real noise spectrum.
    """
    if jitter_px <= 0.0:
        return np.zeros_like(t_values)
    t_max = float(t_values[-1])
    n_ctrl = max(int(t_max / control_spacing_px) + 2, 2)
    ctrl_t = np.linspace(0.0, t_max, n_ctrl)
    ctrl_offsets = rng.normal(0.0, jitter_px, size=n_ctrl)
    ctrl_offsets[0] = 0.0  # anchor the start point exactly
    return np.interp(t_values, ctrl_t, ctrl_offsets)


def _draw_rotated_arm(
    img: np.ndarray,
    start_rc: tuple[float, float],
    bearing_deg: float,
    length: float,
    thickness: int,
    fg_value: float,
    jitter_px: float = 0.0,
    rng_seed: int = 0,
) -> None:
    """Fill a thickness-wide rectangle from start_rc extending `length` px
    in direction `bearing_deg` (0 deg = +col, measured counterclockwise in
    array-index space, i.e. towards -row). Uses skimage.draw.polygon on the
    4 rectangle corners -- an exact fill, so the ground-truth angle carries
    no extra rasterization bias beyond pixel discretization itself.

    `jitter_px > 0` perturbs the arm's centerline with smooth, spatially-
    correlated lateral noise (see _smooth_jitter_1d), seeded by `rng_seed`
    for reproducibility, before filling a thickness-band strip around it --
    a model of realistic skeletonization wobble with a known nominal
    ground truth, NOT a claim about the exact pixel-level boundary of any
    real crack. It exists so the tangent-fit estimator's robustness to
    jitter can be measured (see scripts/window_sweep.py) instead of
    asserted. The start point (t=0) is always exact/unperturbed, so
    `bearing_deg` remains the nominal ground-truth direction at the vertex.
    """
    theta = np.radians(bearing_deg)
    direction = np.array([-np.sin(theta), np.cos(theta)])  # (drow, dcol)
    normal = np.array([direction[1], -direction[0]])  # perpendicular, unit
    start = np.array(start_rc, dtype=np.float64)
    half_t = thickness / 2.0

    if jitter_px <= 0.0:
        end = start + direction * length
        corners = np.array(
            [
                start + normal * half_t,
                end + normal * half_t,
                end - normal * half_t,
                start - normal * half_t,
            ]
        )
        rr, cc = polygon(corners[:, 0], corners[:, 1], shape=img.shape)
        img[rr, cc] = fg_value
        return

    rng = np.random.default_rng(rng_seed)
    n_steps = max(int(round(length)), 4)
    ts = np.linspace(0.0, length, n_steps + 1)
    lateral = _smooth_jitter_1d(ts, jitter_px, rng)
    centerline = start[None, :] + ts[:, None] * direction[None, :] + lateral[:, None] * normal[None, :]
    left = centerline + normal[None, :] * half_t
    right = centerline - normal[None, :] * half_t
    boundary = np.concatenate([left, right[::-1]], axis=0)
    rr, cc = polygon(boundary[:, 0], boundary[:, 1], shape=img.shape)
    img[rr, cc] = fg_value


def generate_t_junction(
    size: int = 120,
    thickness: int = 5,
    margin: int = 10,
    angle_deg: float = 90.0,
    arm_length: float | None = None,
    fg_value: float = 230.0,
    bg_value: float = 10.0,
    jitter_px: float = 0.0,
    rng_seed: int = 0,
) -> np.ndarray:
    """Grayscale image with exactly one T-junction.

    A horizontal "host" line spans the image width (inset by `margin` on
    each side); a straight "abutter" line meets it from above at the host's
    midpoint, at `angle_deg` measured from the host's own bearing (0 deg),
    and stops there (does not cross through) -- forming exactly one 3-way
    junction, with three endpoints (both host ends and the abutter's free
    end). `angle_deg=90.0` (the default) reproduces a plain right-angle T.
    """
    img = np.full((size, size), bg_value, dtype=np.float64)
    mid = size // 2
    half_t = thickness // 2

    if jitter_px <= 0.0:
        # unchanged from the original construction so the existing topology
        # test's assumptions are untouched.
        img[mid - half_t : mid + half_t + 1, margin : size - margin] = fg_value
    else:
        # Host jitter model: smooth (spatially-correlated) lateral wobble
        # of the row-band, anchored at the midpoint (the future junction
        # vertex) and extended outward in both directions -- see
        # _smooth_jitter_1d and _draw_rotated_arm's docstring for why
        # smooth, not independent-per-column, noise is used.
        rng = np.random.default_rng(rng_seed)
        right_cols = np.arange(mid, size - margin)
        left_cols = np.arange(mid, margin - 1, -1)
        right_t = (right_cols - mid).astype(np.float64)
        left_t = (mid - left_cols).astype(np.float64)
        right_off = np.round(_smooth_jitter_1d(right_t, jitter_px, rng)).astype(int)
        left_off = np.round(_smooth_jitter_1d(left_t, jitter_px, rng)).astype(int)
        for cols, offs in ((right_cols, right_off), (left_cols, left_off)):
            for col, off in zip(cols, offs):
                row_lo = np.clip(mid - half_t + off, 0, size - 1)
                row_hi = np.clip(mid + half_t + off, 0, size - 1)
                img[row_lo : row_hi + 1, col] = fg_value

    if arm_length is None:
        arm_length = size / 2.0 - margin

    col_mid = size // 2
    # abutter starts at the host midpoint and points "backwards" along
    # angle_deg from the host's own bearing (host bearing = 0 deg, i.e.
    # +col); angle_deg=90 points straight up (-row), matching the original
    # vertical abutter.
    _draw_rotated_arm(
        img,
        start_rc=(float(mid), float(col_mid)),
        bearing_deg=180.0 - angle_deg,
        length=arm_length,
        thickness=thickness,
        fg_value=fg_value,
        jitter_px=jitter_px,
        rng_seed=rng_seed + 1,  # decorrelate abutter noise from host noise
    )

    return img


def generate_curved_t_junction(
    size: int = 200,
    thickness: int = 5,
    radius: float = 30.0,
    arc_half_angle_deg: float = 75.0,
    abutter_length: float = 50.0,
    fg_value: float = 230.0,
    bg_value: float = 10.0,
    jitter_px: float = 0.0,
    rng_seed: int = 0,
) -> np.ndarray:
    """Grayscale image with one T-junction whose host is a circular arc.

    The host is an arc of a circle of the given `radius`; the abutter is a
    straight arm meeting the arc's midpoint radially from the convex side
    (perpendicular to the local tangent). Ground truth at the junction:
    host tangents exactly 180 deg apart, abutter at 90 deg to each, host
    curvature magnitude exactly 1/radius (opposite signs on the two arms,
    since they are traversed in opposite directions from the vertex).

    The default radius=30 is chosen so a chord over a ~20 px annulus
    subtends enough arc (~38 deg) that a chord-based direction estimate
    provably misclassifies this as "ambiguous" (host pair reads ~152 deg,
    28 deg short of straight, beyond the 20 deg T-straight tolerance),
    while a tangent fit must recover ~180 deg and classify it as a T.
    """
    img = np.full((size, size), bg_value, dtype=np.float64)
    row_c, col_c = size * 0.3, size / 2.0

    rr, cc = np.mgrid[0:size, 0:size]
    d = np.hypot(rr - row_c, cc - col_c)
    # phi = 0 at the arc's lowest point (largest row), growing toward +col
    phi = np.degrees(np.arctan2(cc - col_c, rr - row_c))
    if jitter_px > 0.0:
        # Smooth radial wobble as a function of phi (arc-length analogue
        # of _smooth_jitter_1d), anchored to 0 at phi=0 (the future
        # junction vertex) -- see _draw_rotated_arm's docstring for why
        # smooth, not independent-per-pixel, noise is used.
        rng = np.random.default_rng(rng_seed)
        phi_grid = np.linspace(0.0, arc_half_angle_deg, 200)
        arc_len_grid = np.radians(phi_grid) * radius
        half_offsets = _smooth_jitter_1d(arc_len_grid, jitter_px, rng)
        # phi is signed; mirror the (phi>=0)-anchored offsets onto phi<0
        # using |phi| so both sides still meet exactly at phi=0.
        radial_noise = np.interp(np.abs(phi), phi_grid, half_offsets)
        d = d + radial_noise
    band = (np.abs(d - radius) <= thickness / 2.0) & (np.abs(phi) <= arc_half_angle_deg)
    img[band] = fg_value

    # abutter: radially outward (straight "down") from the arc midpoint
    junction_rc = (row_c + radius, col_c)
    _draw_rotated_arm(
        img,
        start_rc=junction_rc,
        bearing_deg=-90.0,
        length=abutter_length,
        thickness=thickness,
        fg_value=fg_value,
        jitter_px=jitter_px,
        rng_seed=rng_seed + 1,
    )
    return img


def generate_kinked_line(
    size: int = 120,
    thickness: int = 5,
    turn_deg: float = 60.0,
    arm_length: float = 40.0,
    fg_value: float = 230.0,
    bg_value: float = 10.0,
) -> np.ndarray:
    """Grayscale image of a single bent line: two straight arms meeting at
    a known interior corner. No third crack, so the corner is a degree-2
    skeleton point (NOT a junction node) -- exactly the fused-two-cracks
    case the kink scan must flag. `turn_deg` is the direction change
    experienced when traveling through the corner (0 = straight line).
    """
    img = np.full((size, size), bg_value, dtype=np.float64)
    corner = (size / 2.0, size / 2.0)
    # traveling west -> east: enter the corner heading 0 deg, leave heading
    # -turn_deg, so the direction change at the corner is exactly turn_deg.
    _draw_rotated_arm(img, corner, bearing_deg=180.0, length=arm_length,
                      thickness=thickness, fg_value=fg_value)
    _draw_rotated_arm(img, corner, bearing_deg=-float(turn_deg), length=arm_length,
                      thickness=thickness, fg_value=fg_value)
    return img


def generate_straight_line(
    size: int = 120,
    thickness: int = 7,
    length: float | None = None,
    bearing_deg: float = 0.0,
    fg_value: float = 230.0,
    bg_value: float = 10.0,
) -> np.ndarray:
    """Grayscale image of a single straight arm with no junction at all.

    Used as the "nothing to compete with" ground-truth fixture for
    edge_metrics.py: with only one skeleton path in the whole image, the
    watershed area partition has exactly one seed, so area_px2 must equal
    mask_clean.sum() exactly, and the ribbon-integral estimate has no
    neighboring junction blob to double-count -- the case where the area
    methods should have nothing to disagree about.
    """
    img = np.full((size, size), bg_value, dtype=np.float64)
    if length is None:
        length = size * 0.6
    center = np.array([size / 2.0, size / 2.0])
    theta = np.radians(bearing_deg)
    direction = np.array([-np.sin(theta), np.cos(theta)])  # (drow, dcol), same convention as _draw_rotated_arm
    start = center - direction * (length / 2.0)
    _draw_rotated_arm(
        img,
        start_rc=start,
        bearing_deg=bearing_deg,
        length=length,
        thickness=thickness,
        fg_value=fg_value,
    )
    return img


def generate_double_t_junction(
    size: int = 120,
    thickness: int = 5,
    margin: int = 10,
    gap_px: float = 6.0,
    arm_length: float = 30.0,
    fg_value: float = 230.0,
    bg_value: float = 10.0,
) -> np.ndarray:
    """Grayscale image with TWO T-junctions close together on the same host
    line, separated by `gap_px`.

    Used by edge_metrics.py's tests as the canonical "no defensible core
    area" fixture: the host segment between the two junctions is short
    enough that both junctions' blob-disks (edge_metrics.py's
    AREA_JUNCTION_BLOB_RADIUS_PLACEHOLDER, widened by local medial_radius)
    spatially overlap over it, double-claiming the same middle-segment
    pixels -- exactly the case area_core_px2 must clamp to 0 for, rather
    than go negative. The middle segment is a junction-to-junction branch
    (skan branch_type 2), never touched by spur/fragment pruning regardless
    of length, so it survives in the graph at any spur_px.
    """
    img = np.full((size, size), bg_value, dtype=np.float64)
    mid = size // 2
    half_t = thickness // 2
    img[mid - half_t : mid + half_t + 1, margin : size - margin] = fg_value

    col_a = size // 2 - int(round(gap_px / 2))
    col_b = size // 2 + int(round(gap_px / 2))
    for col in (col_a, col_b):
        _draw_rotated_arm(
            img,
            start_rc=(float(mid), float(col)),
            bearing_deg=-90.0,
            length=arm_length,
            thickness=thickness,
            fg_value=fg_value,
        )
    return img


def generate_y_junction(
    size: int = 120,
    thickness: int = 5,
    arm_length: float = 40.0,
    bearings_deg: tuple[float, float, float] = (90.0, 210.0, 330.0),
    center: tuple[float, float] | None = None,
    fg_value: float = 230.0,
    bg_value: float = 10.0,
    jitter_px: float = 0.0,
    rng_seed: int = 0,
) -> np.ndarray:
    """Grayscale image with exactly one 3-way junction at arbitrary bearings.

    Three straight arms radiate from a common center at `bearings_deg`
    (default: 120 deg apart, a canonical Y). No host/abutter distinction --
    used both for a genuine Y check and, with non-120-deg-apart bearings,
    to exercise the "ambiguous" (neither T nor Y) classification path.
    """
    img = np.full((size, size), bg_value, dtype=np.float64)
    if center is None:
        center = (size / 2.0, size / 2.0)

    for k, bearing in enumerate(bearings_deg):
        _draw_rotated_arm(
            img,
            start_rc=center,
            bearing_deg=bearing,
            length=arm_length,
            thickness=thickness,
            fg_value=fg_value,
            jitter_px=jitter_px,
            rng_seed=rng_seed + k,  # decorrelate noise across the 3 arms
        )

    return img


def generate_oriented_segment_field(
    size: int = 400,
    n_segments: int = 60,
    thickness: int = 4,
    length_range_px: tuple[float, float] = (25.0, 45.0),
    bearings_deg: list[float] | None = None,
    bearing_weights: list[float] | None = None,
    bearing_jitter_deg: float = 5.0,
    margin_px: float = 20.0,
    fg_value: float = 230.0,
    bg_value: float = 10.0,
    rng_seed: int = 0,
) -> np.ndarray:
    """Grayscale image with `n_segments` independent straight line segments
    at random positions/lengths, each assigned a bearing (mod 180 deg,
    since orientation here is axial) drawn from a controllable mixture --
    the ground-truth fixture for validating a network-orientation/
    anisotropy metric, since no existing generator produces a many-segment
    field with a known bearing *distribution*.

    `bearings_deg=None` (default) draws each segment's bearing from
    Uniform(0, 180) -- a "mudcrack-like" isotropic field with known
    anisotropy index ~0. Passing e.g. `bearings_deg=[0.0]` draws every
    segment at 0 deg plus `bearing_jitter_deg` noise -- a fully aligned
    "rectilinear" field with known anisotropy index ~1. Passing
    `bearings_deg=[0.0, 90.0]` with `bearing_weights` mixes two
    orthogonal populations at a controllable ratio (an orthogonal-grid
    field) -- the equal-weight case is the documented blind spot of a
    2nd-order orientation tensor (see anisotropy.py), and the unequal
    -weight case is the "grid, strong preferred orientation" validated
    case; `bearing_weights=None` splits the entries of `bearings_deg`
    equally.

    Segments are centered at random positions within
    [margin_px, size-margin_px] and may cross or overlap -- this is a
    fixture for orientation-tensor statistics only, not a claim about a
    realistic crack network topology (no junction-census meaning should be
    read from it), the same caveat _draw_rotated_arm's own docstring makes
    for its jitter model.
    """
    img = np.full((size, size), bg_value, dtype=np.float64)
    rng = np.random.default_rng(rng_seed)

    if bearings_deg is not None:
        weights = bearing_weights if bearing_weights is not None else [1.0] * len(bearings_deg)
        weights = np.asarray(weights, dtype=np.float64)
        weights = weights / weights.sum()

    for i in range(n_segments):
        if bearings_deg is None:
            bearing = float(rng.uniform(0.0, 180.0))
        else:
            choice = int(rng.choice(len(bearings_deg), p=weights))
            bearing = bearings_deg[choice] + float(rng.normal(0.0, bearing_jitter_deg))

        length = float(rng.uniform(*length_range_px))
        center = rng.uniform(margin_px, size - margin_px, size=2)

        theta = np.radians(bearing)
        direction = np.array([-np.sin(theta), np.cos(theta)])
        start = center - direction * (length / 2.0)

        _draw_rotated_arm(
            img,
            start_rc=(float(start[0]), float(start[1])),
            bearing_deg=bearing,
            length=length,
            thickness=thickness,
            fg_value=fg_value,
            rng_seed=rng_seed + i + 1,
        )

    return img


# -- Mesh/network generators (crack_stats-scoped: stage 1-3 + flaking only) --


def _default_grid_offsets(n_lines: int, spacing: float, margin: float) -> list[float]:
    return [margin + spacing * (i + 1) for i in range(n_lines)]


def generate_grid(
    size: int = 340,
    n_lines: int = 3,
    spacing: float = 70.0,
    margin: float = 30.0,
    row_ys: list[float] | None = None,
    col_xs: list[float] | None = None,
    thickness: int = 5,
    fg_value: float = 230.0,
    bg_value: float = 10.0,
) -> np.ndarray:
    """Grayscale image of a rectilinear mesh: `n_lines` horizontal + `n_lines`
    vertical straight lines, each spanning the full crop (margin to
    size-margin) so every interior crossing is a degree->=4 junction and
    every line's two ends are free endpoints -- unlike every generator
    above, this models a *network*, the shape crack_stats.xlsx's
    n_edges/giant_component_fraction are actually measuring on a real,
    densely-cracked image.

    Ground truth (exact, from n_h=len(row_ys)/n_v=len(col_xs) alone, since
    every line crosses every line of the other family exactly once):
    interior junctions = n_h*n_v; each horizontal line is cut into
    (n_v+1) segments by the n_v vertical crossings and vice versa, so
    edges = n_h*(n_v+1) + n_v*(n_h+1); free endpoints = 2*(n_h+n_v).
    `row_ys`/`col_xs` default to `n_lines` evenly-spaced offsets at
    `spacing` px apart -- pass them explicitly (and a matching `size`) to
    sweep grid width/density without changing this formula.
    """
    if row_ys is None:
        row_ys = _default_grid_offsets(n_lines, spacing, margin)
    if col_xs is None:
        col_xs = _default_grid_offsets(n_lines, spacing, margin)

    img = np.full((size, size), bg_value, dtype=np.float64)
    half_t = thickness // 2
    for y in row_ys:
        yi = int(round(y))
        img[yi - half_t : yi + half_t + 1, int(margin) : size - int(margin)] = fg_value
    for x in col_xs:
        xi = int(round(x))
        img[int(margin) : size - int(margin), xi - half_t : xi + half_t + 1] = fg_value
    return img


def grid_topology(n_h: int, n_v: int) -> dict[str, int]:
    """Exact node/edge counts for generate_grid's mesh, given only the
    number of lines per axis (see that function's docstring for the
    derivation) -- a pure combinatorial fact of the crossing structure,
    independent of image size/spacing/thickness."""
    n_junctions = n_h * n_v
    n_endpoints = 2 * (n_h + n_v)
    n_edges = n_h * (n_v + 1) + n_v * (n_h + 1)
    return {
        "n_junctions_deg_ge4": n_junctions,
        "n_endpoints": n_endpoints,
        "n_edges": n_edges,
    }


def generate_wavy_grid(
    size: int = 340,
    n_lines: int = 3,
    spacing: float = 70.0,
    margin: float = 30.0,
    row_ys: list[float] | None = None,
    col_xs: list[float] | None = None,
    thickness: int = 5,
    amplitude: float = 10.0,
    wavelength: float = 110.0,
    fg_value: float = 230.0,
    bg_value: float = 10.0,
) -> np.ndarray:
    """Same row_ys/col_xs as generate_grid (horizontal lines follow a sine
    wave in y instead of running straight; vertical lines stay straight),
    but topology is **not** the same as the straight grid's, and that
    turned out to be the interesting empirical result, not a bug to chase
    away: a degree->=4 skeleton crossing is a non-generic, unstable
    configuration -- verified directly (see tests/test_grid_synthetic.py)
    that even a small amount of local tilt at a crossing resolves it into
    a *pair* of degree-3 points instead of one clean degree-4 point, the
    same "double junction" splitting documented elsewhere in this module
    (generate_double_t_junction) and in skeleton.py, now showing up
    unprompted on a mesh instead of being deliberately constructed. Only
    crossings that happen to land near the wave's own zero-slope points
    stay as a single clean junction; how many of the n_h*n_v crossings
    split grows with `amplitude` and saturates once every crossing has
    enough local tilt (empirically, all at this size=340 default: 3/9
    split at amplitude=2px, 6/9 from amplitude=4px up).

    That saturation point is itself scale-sensitive, not a fixed ratio of
    this shape: uniformly scaling every linear parameter 2x-3x (bigger
    size/spacing/margin/amplitude/wavelength, same relative geometry)
    measured 9/9 crossings splitting instead of 6/9 -- i.e. some of the
    "clean" survivors at this default size were themselves an artifact of
    too little pixel resolution to register their true (small) tilt, not
    a stable exception. Read the 6/9 figure as true only at this specific
    size, not as this wave's asymptotic behavior.

    Exercises the one thing generate_grid can't: whether skeletonization
    and the length/width columns stay accurate on a curved, not just
    straight, mesh -- real crack networks are never perfectly rectilinear.
    Ground-truth *length* of one wavy line is the arc length of
    y = row_y + amplitude*sin(2*pi*(x-margin)/wavelength) over its run,
    computable exactly by numerical integration (see
    wavy_line_arc_length_px below) -- independent of this rasterization.
    """
    if row_ys is None:
        row_ys = _default_grid_offsets(n_lines, spacing, margin)
    if col_xs is None:
        col_xs = _default_grid_offsets(n_lines, spacing, margin)

    img = np.full((size, size), bg_value, dtype=np.float64)
    half_t = thickness // 2
    x0, x1 = int(margin), size - int(margin)
    xs = np.arange(x0, x1)
    for row_y in row_ys:
        ys = row_y + amplitude * np.sin(2.0 * np.pi * (xs - x0) / wavelength)
        for x, y in zip(xs, ys):
            yi = int(round(y))
            img[yi - half_t : yi + half_t + 1, x] = fg_value
    for x in col_xs:
        xi = int(round(x))
        img[int(margin) : size - int(margin), xi - half_t : xi + half_t + 1] = fg_value
    return img


def wavy_line_arc_length_px(run_px: float, amplitude: float, wavelength: float) -> float:
    """Exact (numerically-integrated) arc length of
    y = amplitude*sin(2*pi*x/wavelength) for x in [0, run_px] -- the
    closed-form ground truth generate_wavy_grid's horizontal lines are
    checked against, independent of any rasterization/skeletonization."""
    from scipy.integrate import quad

    def integrand(x: float) -> float:
        dy_dx = amplitude * (2.0 * np.pi / wavelength) * np.cos(2.0 * np.pi * x / wavelength)
        return math.sqrt(1.0 + dy_dx * dy_dx)

    length, _ = quad(integrand, 0.0, run_px)
    return length


def _hexagon_corners(center: tuple[float, float], radius: float) -> list[tuple[float, float]]:
    """Pointy-top hexagon corners (row, col), radius = center-to-corner."""
    return [
        (
            center[0] + radius * math.sin(math.radians(angle)),
            center[1] + radius * math.cos(math.radians(angle)),
        )
        for angle in (30.0, 90.0, 150.0, 210.0, 270.0, 330.0)
    ]


def _hex_flower_centers(center: tuple[float, float], radius: float) -> list[tuple[float, float]]:
    """1 central hexagon + 6 edge-sharing neighbors (a honeycomb 'flower'),
    pointy-top layout -- neighbor centers are radius*sqrt(3) away, evenly
    spaced every 60 deg."""
    d = radius * math.sqrt(3.0)
    neighbors = [
        (
            center[0] + d * math.sin(math.radians(angle)),
            center[1] + d * math.cos(math.radians(angle)),
        )
        for angle in (0.0, 60.0, 120.0, 180.0, 240.0, 300.0)
    ]
    return [center] + neighbors


def hex_flower_topology(radius: float = 40.0, round_ndigits: int = 3) -> dict[str, int]:
    """Exact node/edge counts of a 7-hexagon flower, in skan's own terms
    (endpoint = degree 1, junction = degree >= 3, a degree-2 vertex is a
    mid-edge bend absorbed into whichever edge passes through it, not a
    node) -- computed from the identical corner/center geometry
    generate_hexagonal_grid rasterizes, not hand-counted.

    The 24 raw hexagon corners (6 per hexagon x 7 hexagons, deduplicated
    by rounding to `round_ndigits` decimals where shared) split into 12
    degree-3 vertices (where 3 hexagons meet -- always true junctions) and
    12 degree-2 vertices (the flower's own outer rim, where only 2 hexagon
    edges meet at an angle -- a bend, not a junction). Collapsing each
    degree-2 vertex into its neighbors' edge -- the same reduction skan
    performs -- leaves 12 junction nodes, 0 endpoints (nothing in this
    shape ever dead-ends), and 18 edges. This is a pure fact of the
    flower's combinatorics, independent of `radius` itself, since every
    hexagon is congruent and shares exactly one edge with each neighbor.
    """
    centers = _hex_flower_centers((0.0, 0.0), radius)
    adjacency: dict[tuple[float, float], set[tuple[float, float]]] = {}
    for c in centers:
        corners = [tuple(round(v, round_ndigits) for v in pt) for pt in _hexagon_corners(c, radius)]
        for i in range(6):
            a, b = corners[i], corners[(i + 1) % 6]
            adjacency.setdefault(a, set()).add(b)
            adjacency.setdefault(b, set()).add(a)

    degree = {v: len(neighbors) for v, neighbors in adjacency.items()}
    nodes = {v for v, d in degree.items() if d != 2}

    visited_edges: set[frozenset] = set()
    n_edges = 0
    for start in nodes:
        for first_hop in adjacency[start]:
            edge_key = frozenset((start, first_hop))
            if edge_key in visited_edges:
                continue
            prev, cur = start, first_hop
            path_edges = [edge_key]
            while degree[cur] == 2:
                nxt = next(x for x in adjacency[cur] if x != prev)
                path_edges.append(frozenset((cur, nxt)))
                prev, cur = cur, nxt
            visited_edges.update(path_edges)
            n_edges += 1

    return {
        "n_endpoints": sum(1 for v in nodes if degree[v] == 1),
        "n_junctions_deg3": sum(1 for v in nodes if degree[v] == 3),
        "n_junctions_deg_ge4": sum(1 for v in nodes if degree[v] >= 4),
        "n_edges": n_edges,
    }


def generate_hexagonal_grid(
    size: int = 340,
    radius: float = 40.0,
    thickness: int = 5,
    fg_value: float = 230.0,
    bg_value: float = 10.0,
) -> np.ndarray:
    """Grayscale image of a 7-hexagon honeycomb flower (1 central hexagon +
    6 edge-sharing neighbors), centered in the image.

    Unlike generate_grid's degree->=4 crossings, every interior vertex here
    is degree-3 -- the topology CLAUDE.md's own reference spine (Goehring
    2012) frames real mudcracks as evolving *toward* from an initial
    rectilinear pattern, and structurally the far more common real-crack
    junction valence (two cracks essentially never meet at one point
    simultaneously the way a rectilinear grid assumes). Ideal ground truth
    is hex_flower_topology(radius), built from the exact same corner/center
    geometry drawn here, not a separate guess -- each hexagon edge is drawn
    exactly once even where two hexagons share it (deduplicated the same
    way hex_flower_topology dedupes it, so the two can't silently drift
    apart).

    That ideal count (12 junctions, 18 edges) is not quite what real
    skeletonization measures, and -- as with generate_wavy_grid -- the gap
    is itself the finding: rasterizing each hexagon edge as its own
    independent thick rectangle (via _draw_rotated_arm, no mitered join)
    leaves 2 of the flower's 12 true vertices as a locally *wider* blob
    where 3 rectangles overlap at a shallow angle, and skeletonizing a
    wide blob -- exactly as generate_double_t_junction demonstrates on
    purpose elsewhere -- splits it into two adjacent nodes ~1px apart
    instead of one point. Verified directly (see
    tests/test_grid_synthetic.py) at radius 40/60/80px alike: 14 junctions
    (all degree-3) and 21 edges, stable regardless of radius across that
    specific range, at thickness=5.

    Do not extrapolate this "stable" claim past radius 80: an exploratory
    check at radius=120 (still thickness=5) resolved cleanly to the ideal
    12/18 instead, so this is a real but resolution-sensitive rendering
    effect, not a fixed property of the honeycomb shape -- the 14/21 value
    is only locked in (by the pytest suite) over the 40-80px range it was
    actually tested at.
    """
    center_rc = (size / 2.0, size / 2.0)
    centers = _hex_flower_centers(center_rc, radius)
    img = np.full((size, size), bg_value, dtype=np.float64)
    drawn: set[frozenset] = set()
    for c in centers:
        corners = _hexagon_corners(c, radius)
        for i in range(6):
            a, b = corners[i], corners[(i + 1) % 6]
            key = frozenset(
                (tuple(round(v, 3) for v in a), tuple(round(v, 3) for v in b))
            )
            if key in drawn:
                continue
            drawn.add(key)
            length = math.hypot(b[0] - a[0], b[1] - a[1])
            bearing_deg = math.degrees(math.atan2(-(b[0] - a[0]), b[1] - a[1]))
            _draw_rotated_arm(
                img, start_rc=a, bearing_deg=bearing_deg, length=length,
                thickness=thickness, fg_value=fg_value,
            )
    return img


def generate_grid_with_flakes(
    size: int = 340,
    n_lines: int = 3,
    spacing: float = 70.0,
    margin: float = 30.0,
    thickness: int = 5,
    flake_centers: list[tuple[float, float]] | None = None,
    flake_radius: float = 26.0,
    fg_value: float = 230.0,
    bg_value: float = 10.0,
) -> np.ndarray:
    """generate_grid's mesh, with circular filled disks ("flakes") stamped
    on top at `flake_centers` -- bright under the same threshold as real
    crack, exactly the delamination case flaking.py exists for (see its
    module docstring and CLAUDE.md's flaking/delamination section): a 2D
    area of missing material, not a 1D fracture, wide enough
    (2*flake_radius) relative to `thickness` to trip flaking.py's
    width-based candidate identification. Defaults to one flake centered on
    an interior grid junction (where real delamination is most likely to
    swallow crack topology) if `flake_centers` isn't given.

    Ground truth for the *true* flaked pixel area is deliberately not
    returned here -- reconstruct it the same way every other case in this
    module does, by drawing the disks alone on a blank canvas with
    skimage.draw.disk at the same `flake_centers`/`flake_radius` and
    summing the boolean mask, so a caller can compare it against
    flaking.py's own recovered `excluded_area_px2` without trusting this
    function's bookkeeping.
    """
    if flake_centers is None:
        row_ys = _default_grid_offsets(n_lines, spacing, margin)
        col_xs = _default_grid_offsets(n_lines, spacing, margin)
        mid = n_lines // 2
        flake_centers = [(row_ys[mid], col_xs[mid])]

    img = generate_grid(
        size=size, n_lines=n_lines, spacing=spacing, margin=margin,
        thickness=thickness, fg_value=fg_value, bg_value=bg_value,
    )
    for cy, cx in flake_centers:
        rr, cc = disk((cy, cx), flake_radius, shape=img.shape)
        img[rr, cc] = fg_value
    return img
