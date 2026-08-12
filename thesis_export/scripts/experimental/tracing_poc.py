"""Bare-minimum, throwaway proof of concept for the tracing idea in
docs/dynamic_tracking_hypothetical.md Sec. 5 ("a no-matrix alternative to
Steger's method").

**Nothing here is validated or integrated with the real pipeline.** It exists
to answer one question cheaply: does a greedy, curvature-of-radius-profile
costed path search walk a sane path along the medial axis of a solid blob, on
the simplest possible synthetic shapes -- without ever calling the expensive
iterative skimage.morphology.skeletonize() as part of the trace itself?

skimage.morphology.skeletonize() is still called once per shape, but only as
a ground-truth reference drawn alongside the traced path for visual
comparison -- using it inside the tracer would defeat the point.

Three shapes, each isolating one of the three failure modes of a naive
"step to the neighbor with the highest local radius" tracer (see the doc's
Sec. 4):

- triangle: medial axis narrows to a point at the apex -> tests wrong-way
  pull near a real tip.
- rectangle: medial axis is flat/constant-width down the middle -> tests
  zigzag/no-forward-signal on a flat radius profile.
- L-shape (90-degree turn): medial axis bends sharply at the corner -> tests
  following a genuine direction change.

No fork/branch case: none of these three shapes branches, so the annulus /
fork-spawning machinery from Sec. 5 is out of scope here.

The tracer is greedy with a 1-step lookahead, not full Dijkstra/A* to a known
target -- a deliberate v0 simplification, since these are clean, noiseless
synthetic masks. If this doesn't already show the right qualitative
behaviour, a multi-step search (as the doc actually proposes) is the next
thing to try, not a tweak to this greedy version.

Run: python scripts/experimental/tracing_poc.py
Output: outputs/tracing_poc.png
"""

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import distance_transform_edt
from skimage.draw import polygon
from skimage.morphology import skeletonize

OUT_PATH = Path("outputs/tracing_poc.png")

STEP_PX = 3.0
CONE_DEG = 90.0
ANGLE_STEP_DEG = 8.0
MOMENTUM_WEIGHT = 1.0
MAX_STEPS = 500
# Seed points sit a few step_px in from the shape's near edge, not right on
# it -- right at the boundary the radius is ~0 by construction, which would
# trip the "radius_near_zero" termination check on the very first step.
SEED_INSET_PX = 3.0 * STEP_PX


# ---------------------------------------------------------------------------
# Shape generators. All build a (size, size) boolean mask via
# skimage.draw.polygon on hand-specified vertices -- no generator like this
# exists in src/crackgraph/synthetic.py, whose generators are all thin
# constant-thickness line arms, not filled blobs.
# ---------------------------------------------------------------------------


def make_triangle(size, base_width, height):
    """Isosceles triangle, base centered along the bottom, apex at the top.

    Returns (mask, seed_rc, initial_direction): seed is the midpoint of the
    base, heading straight up toward the apex.
    """
    mask = np.zeros((size, size), dtype=bool)
    cx = size / 2.0
    base_row = size - 10
    apex_row = base_row - height
    r = [base_row, base_row, apex_row]
    c = [cx - base_width / 2.0, cx + base_width / 2.0, cx]
    rr, cc = polygon(r, c, shape=mask.shape)
    mask[rr, cc] = True
    seed_rc = (base_row - SEED_INSET_PX, cx)
    direction = (-1.0, 0.0)
    return mask, seed_rc, direction


def make_rectangle(size, width, height):
    """Centered filled rectangle, long axis vertical.

    Seed is the midpoint of the bottom short edge, heading up the long axis.
    """
    mask = np.zeros((size, size), dtype=bool)
    cx = size / 2.0
    cy = size / 2.0
    r0, r1 = cy - height / 2.0, cy + height / 2.0
    c0, c1 = cx - width / 2.0, cx + width / 2.0
    r = [r0, r0, r1, r1]
    c = [c0, c1, c1, c0]
    rr, cc = polygon(r, c, shape=mask.shape)
    mask[rr, cc] = True
    seed_rc = (r1 - SEED_INSET_PX, cx)
    direction = (-1.0, 0.0)
    return mask, seed_rc, direction


def make_l_shape(size, arm_width, arm1_len, arm2_len):
    """Two filled rectangles sharing a corner: one vertical arm rising from
    the bottom-left, one horizontal arm extending right from the top of the
    vertical arm, forming a 90-degree bend.

    Seed is the far (bottom) end of the vertical arm, heading up into the
    bend; the trace is expected to turn 90 degrees and continue along the
    horizontal arm.
    """
    mask = np.zeros((size, size), dtype=bool)
    margin = 10.0
    col0 = margin
    row_bottom = size - margin
    row_top = row_bottom - arm1_len

    # vertical arm
    r = [row_top, row_top, row_bottom, row_bottom]
    c = [col0, col0 + arm_width, col0 + arm_width, col0]
    rr, cc = polygon(r, c, shape=mask.shape)
    mask[rr, cc] = True

    # horizontal arm, extending right from the top of the vertical arm
    r = [row_top, row_top, row_top + arm_width, row_top + arm_width]
    c = [col0, col0 + arm2_len, col0 + arm2_len, col0]
    rr, cc = polygon(r, c, shape=mask.shape)
    mask[rr, cc] = True

    seed_rc = (row_bottom - SEED_INSET_PX, col0 + arm_width / 2.0)
    direction = (-1.0, 0.0)
    return mask, seed_rc, direction


def _triangle_polygon(base_center_rc, base_half_width, apex_rc):
    """3 vertices (r_coords, c_coords) for a triangle: a base perpendicular
    to the base->apex axis, plus the apex point."""
    direction = _normalize(
        (apex_rc[0] - base_center_rc[0], apex_rc[1] - base_center_rc[1])
    )
    perp = (-direction[1], direction[0])
    b1 = (
        base_center_rc[0] + perp[0] * base_half_width,
        base_center_rc[1] + perp[1] * base_half_width,
    )
    b2 = (
        base_center_rc[0] - perp[0] * base_half_width,
        base_center_rc[1] - perp[1] * base_half_width,
    )
    return [b1[0], b2[0], apex_rc[0]], [b1[1], b2[1], apex_rc[1]]


def make_rod_two_triangles(size, rod_half_width, rod_length, triangle_len):
    """A straight rod (rectangle) with a triangular point at both ends.

    Tests a full pass through a widen-then-narrow profile in one continuous
    trace: flat body in the middle, tapering tips at both ends. Seed sits
    inside the left tip, heading right; the trace is expected to cross the
    whole body and terminate at the right tip's apex.
    """
    mask = np.zeros((size, size), dtype=bool)
    cy = size / 2.0
    c0 = (size - rod_length) / 2.0
    c1 = c0 + rod_length

    r = [cy - rod_half_width, cy - rod_half_width, cy + rod_half_width, cy + rod_half_width]
    c = [c0, c1, c1, c0]
    rr, cc = polygon(r, c, shape=mask.shape)
    mask[rr, cc] = True

    left_apex = (cy, c0 - triangle_len)
    r, c = _triangle_polygon((cy, c0), rod_half_width, left_apex)
    rr, cc = polygon(r, c, shape=mask.shape)
    mask[rr, cc] = True

    right_apex = (cy, c1 + triangle_len)
    r, c = _triangle_polygon((cy, c1), rod_half_width, right_apex)
    rr, cc = polygon(r, c, shape=mask.shape)
    mask[rr, cc] = True

    inset = max(SEED_INSET_PX, 0.3 * triangle_len)
    seed_rc = (cy, left_apex[1] + inset)
    direction = (0.0, 1.0)
    return mask, seed_rc, direction


def make_rod_one_triangle(size, rod_half_width, rod_length, triangle_len):
    """A straight rod with a flat end on one side and a triangular point on
    the other -- a pencil/arrow shape. Seed sits just inside the flat end,
    heading toward the point.
    """
    mask = np.zeros((size, size), dtype=bool)
    cy = size / 2.0
    c0 = (size - rod_length - triangle_len) / 2.0
    c1 = c0 + rod_length

    r = [cy - rod_half_width, cy - rod_half_width, cy + rod_half_width, cy + rod_half_width]
    c = [c0, c1, c1, c0]
    rr, cc = polygon(r, c, shape=mask.shape)
    mask[rr, cc] = True

    apex = (cy, c1 + triangle_len)
    r, c = _triangle_polygon((cy, c1), rod_half_width, apex)
    rr, cc = polygon(r, c, shape=mask.shape)
    mask[rr, cc] = True

    seed_rc = (cy, c0 + SEED_INSET_PX)
    direction = (0.0, 1.0)
    return mask, seed_rc, direction


def make_curved_rod_two_triangles(
    size, center_rc, radius, thickness, half_span_deg, triangle_len
):
    """A curved rod (a constant-width band along a circular arc, bowing
    upward like an arch) with a triangular point at both ends -- combines
    curve-following with tip-convergence in one continuous trace.

    theta is measured from the arc's own "straight up" direction (90 deg in
    standard math-angle convention over (col, -row)); the arc spans
    [90-half_span_deg, 90+half_span_deg]. Tangent directions at each end are
    found numerically (sample a point 1 degree further outward along the
    same circle and take the difference), rather than derived symbolically,
    to avoid a sign-convention mistake.
    """
    mask = np.zeros((size, size), dtype=bool)
    rows, cols = np.mgrid[0:size, 0:size]
    dr = rows - center_rc[0]
    dc = cols - center_rc[1]
    rho = np.sqrt(dr**2 + dc**2)
    theta = np.degrees(np.arctan2(-dr, dc))
    theta0, theta1 = 90.0 - half_span_deg, 90.0 + half_span_deg
    band = (np.abs(rho - radius) <= thickness / 2.0) & (theta >= theta0) & (theta <= theta1)
    mask |= band

    def arc_point(theta_deg):
        t = math.radians(theta_deg)
        return (center_rc[0] - radius * math.sin(t), center_rc[1] + radius * math.cos(t))

    p0 = arc_point(theta0)
    tangent0 = _normalize(
        (arc_point(theta0 - 1.0)[0] - p0[0], arc_point(theta0 - 1.0)[1] - p0[1])
    )
    apex0 = (p0[0] + tangent0[0] * triangle_len, p0[1] + tangent0[1] * triangle_len)
    r, c = _triangle_polygon(p0, thickness / 2.0, apex0)
    rr, cc = polygon(r, c, shape=mask.shape)
    mask[rr, cc] = True

    p1 = arc_point(theta1)
    tangent1 = _normalize(
        (arc_point(theta1 + 1.0)[0] - p1[0], arc_point(theta1 + 1.0)[1] - p1[1])
    )
    apex1 = (p1[0] + tangent1[0] * triangle_len, p1[1] + tangent1[1] * triangle_len)
    r, c = _triangle_polygon(p1, thickness / 2.0, apex1)
    rr, cc = polygon(r, c, shape=mask.shape)
    mask[rr, cc] = True

    inset = max(SEED_INSET_PX, 0.3 * triangle_len)
    seed_rc = (apex0[0] - tangent0[0] * inset, apex0[1] - tangent0[1] * inset)
    direction = (-tangent0[0], -tangent0[1])
    return mask, seed_rc, direction


# ---------------------------------------------------------------------------
# The tracer.
# ---------------------------------------------------------------------------


def _normalize(vec):
    norm = math.hypot(vec[0], vec[1])
    if norm < 1e-9:
        return vec
    return (vec[0] / norm, vec[1] / norm)


def _sample_radius(dist, rc):
    row, col = rc
    ri = int(round(row))
    ci = int(round(col))
    if ri < 0 or ci < 0 or ri >= dist.shape[0] or ci >= dist.shape[1]:
        return 0.0
    return float(dist[ri, ci])


def _in_mask(mask, rc):
    row, col = rc
    ri = int(round(row))
    ci = int(round(col))
    if ri < 0 or ci < 0 or ri >= mask.shape[0] or ci >= mask.shape[1]:
        return False
    return bool(mask[ri, ci])


def trace(
    mask,
    dist,
    seed_rc,
    initial_direction,
    *,
    step_px=STEP_PX,
    cone_deg=CONE_DEG,
    angle_step_deg=ANGLE_STEP_DEG,
    momentum_weight=MOMENTUM_WEIGHT,
    max_steps=MAX_STEPS,
):
    """Greedy, 1-step-lookahead path search along the medial axis, costed on
    the local curvature (2nd difference) of the distance-transform radius
    profile plus a directional-momentum tie-breaker.

    Returns (path, reason) where path is a list of (row, col) points
    (including the seed) and reason is one of "radius_near_zero" (reached a
    tip/edge), "no_candidates" (walked into background on all headings), or
    "max_steps" (safety cap hit).
    """
    heading = _normalize(initial_direction)
    path = [seed_rc]
    radii = [_sample_radius(dist, seed_rc)]

    half_cone = cone_deg / 2.0
    n_angles = int(round(cone_deg / angle_step_deg)) + 1
    offsets_deg = np.linspace(-half_cone, half_cone, n_angles)

    for _ in range(max_steps):
        r_curr = radii[-1]
        if r_curr < step_px:
            return path, "radius_near_zero"

        heading_angle = math.atan2(heading[0], heading[1])
        best_cost = None
        best_point = None
        best_heading = None

        for off_deg in offsets_deg:
            angle = heading_angle + math.radians(off_deg)
            step_vec = (math.sin(angle) * step_px, math.cos(angle) * step_px)
            candidate = (path[-1][0] + step_vec[0], path[-1][1] + step_vec[1])

            if not _in_mask(mask, candidate):
                continue

            r_next = _sample_radius(dist, candidate)
            if len(radii) >= 2:
                r_prev = radii[-2]
                curvature_term = abs(r_next - 2.0 * r_curr + r_prev)
            else:
                curvature_term = 0.0

            cand_heading = _normalize(step_vec)
            cos_angle = cand_heading[0] * heading[0] + cand_heading[1] * heading[1]
            cos_angle = max(-1.0, min(1.0, cos_angle))
            momentum_term = 1.0 - cos_angle

            cost = curvature_term + momentum_weight * momentum_term

            if best_cost is None or cost < best_cost:
                best_cost = cost
                best_point = candidate
                best_heading = cand_heading

        if best_point is None:
            return path, "no_candidates"

        path.append(best_point)
        radii.append(_sample_radius(dist, best_point))
        heading = best_heading

    return path, "max_steps"


# ---------------------------------------------------------------------------
# Visualization + entry point.
# ---------------------------------------------------------------------------


def _render_panel(ax, mask, skel, path, title):
    ax.imshow(mask, cmap="gray", origin="upper")

    skel_rr, skel_cc = np.nonzero(skel)
    ax.plot(skel_cc, skel_rr, ".", color="tab:red", markersize=1.5, alpha=0.5,
             label="skeletonize() ground truth")

    path_arr = np.array(path)
    ax.plot(path_arr[:, 1], path_arr[:, 0], "-o", color="lime", linewidth=1.5,
             markersize=3, label="traced path")
    ax.plot(path_arr[0, 1], path_arr[0, 0], "o", color="green", markersize=8,
             label="seed")
    ax.plot(path_arr[-1, 1], path_arr[-1, 0], "x", color="red", markersize=10,
             markeredgewidth=2, label="termination")

    ax.set_title(title)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.legend(fontsize=6, loc="upper right")


def _slugify(name):
    return name.lower().replace(",", "").replace("(", "").replace(")", "").replace(
        " ", "_").replace("-", "_")


def main():
    shapes = [
        ("triangle", *make_triangle(size=150, base_width=80, height=110)),
        ("rectangle", *make_rectangle(size=150, width=30, height=110)),
        ("L-shape (90-deg turn)", *make_l_shape(
            size=150, arm_width=20, arm1_len=90, arm2_len=90)),
        ("rod, triangles both ends", *make_rod_two_triangles(
            size=220, rod_half_width=15, rod_length=90, triangle_len=45)),
        ("curved rod, triangles both ends", *make_curved_rod_two_triangles(
            size=260, center_rc=(220.0, 130.0), radius=150.0, thickness=25.0,
            half_span_deg=40.0, triangle_len=35)),
        ("rod, triangle one end", *make_rod_one_triangle(
            size=220, rod_half_width=15, rod_length=90, triangle_len=45)),
    ]

    fig, axes = plt.subplots(2, 3, figsize=(15, 11))
    axes_flat = axes.flatten()

    panels_dir = OUT_PATH.parent / "tracing_poc_panels"
    panels_dir.mkdir(parents=True, exist_ok=True)

    for ax, (name, mask, seed_rc, direction) in zip(axes_flat, shapes):
        dist = distance_transform_edt(mask)
        skel = skeletonize(mask)
        path, reason = trace(mask, dist, seed_rc, direction)
        print(f"{name}: {len(path)} steps, terminated: {reason}")
        _render_panel(ax, mask, skel, path, f"{name}\n({reason}, {len(path)} steps)")

        single_fig, single_ax = plt.subplots(figsize=(5, 5))
        _render_panel(single_ax, mask, skel, path, "")
        single_ax.set_title("")
        single_fig.tight_layout()
        single_fig.savefig(panels_dir / f"{_slugify(name)}.png", dpi=150)
        plt.close(single_fig)

    fig.tight_layout()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PATH, dpi=150)
    print(f"Saved {OUT_PATH}")


if __name__ == "__main__":
    main()
