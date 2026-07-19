"""Synthetic test image generation: minimal, known-topology/known-angle
junction images.

Used to validate the stage 1-3 chain end-to-end against cases with a known
right answer (exact node/edge counts), and stage 4's annulus angle
measurement against a known ground-truth angle -- rather than just "runs
without crashing" on real data.
"""

import numpy as np
from skimage.draw import polygon


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
