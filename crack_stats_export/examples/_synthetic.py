"""Minimal synthetic-pattern generators, trimmed from the parent project's
`src/crackgraph/synthetic.py` (which has more generators for other pipeline
stages not part of this export -- junction-angle, curvature, kink cases).

Only `generate_straight_line` and `generate_t_junction` are kept here
(verbatim, unedited), because they're the two used by
`generate_examples.py`'s "schematic proof" -- both have an exactly known
ground truth (line length/thickness, or junction edge count/topology) that
the crack_stats.xlsx-style measurements can be checked against. This file
exists only to support `examples/generate_examples.py`; it is not part of
the crack-stats pipeline itself (`export_crack_stats.py` never imports it).
"""

import numpy as np
from skimage.draw import polygon


def _smooth_jitter_1d(
    t_values: np.ndarray,
    jitter_px: float,
    rng: np.random.Generator,
    control_spacing_px: float = 8.0,
) -> np.ndarray:
    """Spatially-correlated lateral noise (unused at jitter_px=0, the only
    value this export's schematic cases use -- kept for fidelity to the
    original generator rather than trimming the jitter code path out)."""
    if jitter_px <= 0.0:
        return np.zeros_like(t_values)
    t_max = float(t_values[-1])
    n_ctrl = max(int(t_max / control_spacing_px) + 2, 2)
    ctrl_t = np.linspace(0.0, t_max, n_ctrl)
    ctrl_offsets = rng.normal(0.0, jitter_px, size=n_ctrl)
    ctrl_offsets[0] = 0.0
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
    in direction `bearing_deg` (0 deg = +col, counterclockwise in array-
    index space). Exact polygon fill -- the ground-truth length/thickness
    carries no extra rasterization bias beyond pixel discretization itself.
    """
    theta = np.radians(bearing_deg)
    direction = np.array([-np.sin(theta), np.cos(theta)])
    normal = np.array([direction[1], -direction[0]])
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


def generate_straight_line(
    size: int = 120,
    thickness: int = 7,
    length: float | None = None,
    bearing_deg: float = 0.0,
    fg_value: float = 230.0,
    bg_value: float = 10.0,
) -> np.ndarray:
    """Grayscale image of a single straight arm with no junction at all --
    ground truth: exactly one skeleton edge of the given `length`, filled
    area exactly `length * thickness` px (up to end-cap rounding)."""
    img = np.full((size, size), bg_value, dtype=np.float64)
    if length is None:
        length = size * 0.6
    center = np.array([size / 2.0, size / 2.0])
    theta = np.radians(bearing_deg)
    direction = np.array([-np.sin(theta), np.cos(theta)])
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
    """Grayscale image with exactly one T-junction -- ground truth: a
    horizontal "host" line spans the image width (inset by `margin`), a
    straight "abutter" meets it from above at the midpoint. Skeletonizing
    this must produce exactly 3 edges (host-left, host-right, abutter), 1
    degree-3 junction node, 3 endpoint nodes, all one connected component.
    """
    img = np.full((size, size), bg_value, dtype=np.float64)
    mid = size // 2
    half_t = thickness // 2

    if jitter_px <= 0.0:
        img[mid - half_t : mid + half_t + 1, margin : size - margin] = fg_value
    else:
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
    _draw_rotated_arm(
        img,
        start_rc=(float(mid), float(col_mid)),
        bearing_deg=180.0 - angle_deg,
        length=arm_length,
        thickness=thickness,
        fg_value=fg_value,
        jitter_px=jitter_px,
        rng_seed=rng_seed + 1,
    )

    return img
