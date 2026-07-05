"""Overlay rendering: skeleton + junction/endpoint markers on the original image.

Analysis always runs at the full resolution of the region being processed.
Only this saved visualization is downsampled, and only the *image
background* is resampled (LANCZOS) -- skeleton/node coordinates are scaled
numerically instead of resampling the (often 1px-wide) skeleton bitmap,
which would blur or break under any resampling filter.

Two views, not one (`detail` flag), because "does this look right" and
"audit the angle estimator" are genuinely different tasks that want
different amounts of information on screen:
- Default (`detail=False`): skeleton, endpoints, classification markers,
  kink flags, corner cross-check markers (including disagreement rings --
  that's a headline signal, not a diagnostic detail), and a short label
  (just the node_id, for cross-referencing the console report) per
  classified junction. This is the quick-look view.
- Detail (`detail=True`): everything above, plus the fitted-curve/tick/
  terminal-segment diagnostic layer and full angle-gap text labels. An
  earlier version drew a fixed-length ray from the extrapolated tangent,
  which could visibly diverge from the actual skeleton -- misleading, and
  hard to tell whether a disagreement was a real estimator problem or just
  an artifact of how it was drawn -- so in detail mode:
  - The cyan curve is the *fitted* quadratic/line evaluated only over the
    band of pixels it was actually fitted to (no extrapolation) -- what is
    drawn IS what was measured, so any visible disagreement with the green
    skeleton is a real, inspectable fit-quality signal, not hidden by the
    renderer.
  - The short cyan tick at the inner end of that curve is the derived
    tangent direction, drawn short on purpose so it isn't mistaken for a
    claim about geometry beyond the fitted band.
  - The dashed grey segment nearest each junction vertex is the part of
    the skeleton path *inside* the effective inner radius (the junction
    blob, possibly widened by the medial-axis half-width -- see
    junctions.py) -- this is where two (or three) thick strokes merge and
    the skeleton is not evidence of any single arm's true path.

The legend is drawn *below* the axes (bbox_to_anchor with a negative y),
not on top of the image -- an earlier version placed it inside the axes at
the top right and it regularly covered real junctions.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import skan
from matplotlib.collections import LineCollection
from PIL import Image

from .corners import CornerCrossCheck
from .graph import GraphResult
from .junctions import JunctionAnalysisResult
from .kinks import KinkScanResult

_LABEL_STYLE = {
    "T": ("tab:blue", "^", "T junction"),
    "Y": ("tab:green", "P", "Y junction"),
    "ambiguous": ("darkorange", "x", "ambiguous junction"),
    "insufficient_data": ("0.5", "x", "junction (insufficient annulus data)"),
}

TANGENT_TICK_LENGTH_PX = 8.0
# Fixed short display length for the tangent-direction tick -- deliberately
# NOT tied to the annulus radius, so it can never be mistaken for a claim
# about how far the fit window reached (see module docstring).

LABEL_OFFSET_VARIANTS_PX = [(6.0, -6.0), (-14.0, 12.0), (14.0, 8.0), (-16.0, -10.0)]
# Candidate (dx, dy) label offsets, in increasing order of preference. A
# single fixed offset (even flipped to the opposite corner) wasn't enough
# separation when 2+ vertices were within a text-box-width of each other --
# the flip only moved the label ~8px, not enough to clear a 3-4 character
# box. Cycling through 4 increasingly-spread-out placements handles small
# local clusters (common in real crack images); beyond 4 mutually-close
# junctions the variants repeat -- a real density limit, not fixable by
# label placement alone.

LABEL_NUDGE_DISTANCE_PX = 20.0
# If a label's vertex is closer than this to an already-placed label's
# vertex, use the next offset variant instead of the default -- a lightweight
# heuristic (not full collision avoidance) that resolves the common
# two-junctions-close-together case.


def _terminal_segment(
    skel: skan.Skeleton, path_index: int, vertex: np.ndarray, effective_inner_radius_px: float
) -> np.ndarray:
    """Raw polyline points within effective_inner_radius_px of `vertex`
    (the part of the skeleton inside the junction blob) -- oriented so the
    first point is at the vertex, for drawing as the dashed "not evidence"
    segment.
    """
    coords = skel.path_coordinates(path_index).astype(np.float64)
    if np.linalg.norm(coords[-1] - vertex) < np.linalg.norm(coords[0] - vertex):
        coords = coords[::-1]
    d = np.linalg.norm(coords - coords[0], axis=1)
    return coords[d <= effective_inner_radius_px]


def render_overlay(
    rgb: np.ndarray,
    skel: skan.Skeleton,
    graph_result: GraphResult,
    out_path: str | Path,
    *,
    max_overlay_dim: int = 2500,
    junction_result: JunctionAnalysisResult | None = None,
    kink_result: KinkScanResult | None = None,
    corner_cross_check: list[CornerCrossCheck] | None = None,
    detail: bool = False,
) -> float:
    """Save an overlay PNG. Returns the scale factor used for the display image.

    `detail=False` (default): clean quick-look view -- classification/
    corner/kink markers and a short node_id label per junction, no fitted-
    curve diagnostics. `detail=True`: adds the fitted-curve/tick/terminal-
    segment layer and switches labels to the full angle-gap text -- see
    module docstring.
    """
    h, w = rgb.shape[:2]
    scale = min(1.0, max_overlay_dim / max(h, w))

    if scale < 1.0:
        new_size = (round(w * scale), round(h * scale))
        display_rgb = np.asarray(Image.fromarray(rgb).resize(new_size, Image.LANCZOS))
    else:
        display_rgb = rgb

    disp_h, disp_w = display_rgb.shape[:2]
    dpi = 150
    fig, ax = plt.subplots(figsize=(disp_w / dpi, disp_h / dpi), dpi=dpi)
    ax.imshow(display_rgb)

    n_edges = len(graph_result.summary)
    if n_edges > 0:
        segments = []
        for i in range(n_edges):
            coords = skel.path_coordinates(i) * scale  # (row, col)
            segments.append(coords[:, ::-1])  # -> (col, row) == (x, y)
        lc = LineCollection(segments, colors="lime", linewidths=0.6, zorder=2)
        ax.add_collection(lc)

    degree = graph_result.node_degree
    coords = graph_result.node_coords * scale  # (row, col)
    endpoints = coords[degree == 1]

    if len(endpoints) > 0:
        ax.scatter(
            endpoints[:, 1], endpoints[:, 0], s=6, c="orange", zorder=3,
            label="endpoint (deg 1)",
        )

    any_junction_marker = len(endpoints) > 0

    if junction_result is None:
        junctions = coords[degree >= 3]
        if len(junctions) > 0:
            ax.scatter(
                junctions[:, 1], junctions[:, 0], s=10, c="red", zorder=4,
                label="junction (deg>=3)",
            )
            any_junction_marker = True
    else:
        deg_ge4 = coords[degree >= 4]
        if len(deg_ge4) > 0:
            ax.scatter(
                deg_ge4[:, 1], deg_ge4[:, 0], s=10, c="red", zorder=4,
                label="junction deg>=4 (unclassified)",
            )
            any_junction_marker = True

        label_by_node = {c.node_id: c.label for c in junction_result.classifications}
        for label, (color, marker, legend) in _LABEL_STYLE.items():
            sel_idx = [
                i
                for i, nid in enumerate(graph_result.node_ids)
                if graph_result.node_degree[i] == 3 and label_by_node.get(int(nid)) == label
            ]
            if sel_idx:
                pts = coords[sel_idx]
                ax.scatter(
                    pts[:, 1], pts[:, 0], s=12, c=color, marker=marker, zorder=5,
                    label=legend,
                )
                any_junction_marker = True

    # Per-junction text labels: short node_id by default (cross-references
    # the console report), full angle-gap text in detail mode. Drawn for
    # every classified junction regardless of `detail` -- only the CONTENT
    # and the extra fitted-curve geometry differ in detail mode.
    if junction_result is not None:
        placed_label_vertices: list[np.ndarray] = []
        for c in junction_result.classifications:
            if c.sector_gaps_deg is None:
                continue  # insufficient_data: no reliable angle info to show
            vertex_full = np.array(c.coord)  # (row, col), full-resolution coords
            vertex = vertex_full * scale
            color = _LABEL_STYLE[c.label][0]

            n_nearby = sum(
                np.linalg.norm(vertex - p) < LABEL_NUDGE_DISTANCE_PX for p in placed_label_vertices
            )
            dx, dy = LABEL_OFFSET_VARIANTS_PX[n_nearby % len(LABEL_OFFSET_VARIANTS_PX)]
            placed_label_vertices.append(vertex)

            label_text = (
                "/".join(f"{g:.0f}°" for g in sorted(c.sector_gaps_deg))
                if detail
                else str(c.node_id)
            )
            ax.annotate(
                label_text,
                xy=(vertex[1], vertex[0]),
                xytext=(vertex[1] + dx, vertex[0] + dy),
                fontsize=6 if not detail else 5,
                color=color,
                zorder=7 + n_nearby,  # later-overlapping labels draw on top, outline keeps them distinguishable
                bbox=dict(boxstyle="round,pad=0.15", fc="black", ec="white", lw=0.4, alpha=0.75),
            )

    if junction_result is not None and detail:
        fit_curve_segments = []
        tick_segments = []
        terminal_segments = []
        for c in junction_result.classifications:
            if c.sector_gaps_deg is None:
                continue  # insufficient_data: no reliable directions to draw
            vertex_full = np.array(c.coord)  # (row, col), full-resolution coords

            for ed in c.edge_directions:
                if ed.direction is None:
                    continue

                # Terminal segment: the part of this arm's skeleton inside
                # the junction blob (< effective inner radius) -- inferred
                # by the medial axis, not evidence of this arm's own path.
                term = _terminal_segment(skel, ed.path_index, vertex_full, ed.effective_inner_radius_px)
                if len(term) >= 2:
                    terminal_segments.append((term * scale)[:, ::-1])

                if ed.fit_coef_row is None or ed.band_s_range is None:
                    continue

                # Fitted curve, drawn ONLY over the band actually fitted
                # (s in [s_min, s_max]) -- no extrapolation, so any visible
                # gap from the green skeleton is a real fit-quality signal.
                s_min, s_max = ed.band_s_range
                s_samples = np.linspace(s_min, s_max, 20)
                curve_row = np.polyval(ed.fit_coef_row, s_samples)
                curve_col = np.polyval(ed.fit_coef_col, s_samples)
                curve = np.stack([curve_row, curve_col], axis=1) * scale
                fit_curve_segments.append(curve[:, ::-1])

                # Short tangent tick at the inner end of the fitted curve.
                tick_start = np.array([curve_row[0], curve_col[0]])
                tick_end = tick_start + ed.direction * TANGENT_TICK_LENGTH_PX
                tick_segments.append(np.stack([tick_start, tick_end])[:, ::-1] * scale)

        if terminal_segments:
            ax.plot([], [], color="0.6", linewidth=1.2, linestyle="--",
                     label="terminal segment (inside junction blob, not evidence)")
            ax.add_collection(
                LineCollection(terminal_segments, colors="0.6", linewidths=1.2,
                               linestyles="dashed", zorder=5)
            )
            any_junction_marker = True

        if fit_curve_segments:
            ax.plot([], [], color="cyan", linewidth=1.0, label="fitted curve (over band actually used)")
            ax.add_collection(
                LineCollection(fit_curve_segments, colors="cyan", linewidths=1.0, zorder=6)
            )
            any_junction_marker = True

        if tick_segments:
            ax.add_collection(
                LineCollection(tick_segments, colors="cyan", linewidths=1.6, zorder=7)
            )

    if corner_cross_check is not None:
        corner_pts = []
        disagree_corner_pts = []
        for cc in corner_cross_check:
            pts = np.array([wc.coord for wc in cc.corners]) * scale if cc.corners else None
            if pts is None or len(pts) == 0:
                continue
            if cc.agrees_with_tangent_fit is False:
                disagree_corner_pts.append(pts)
            else:
                corner_pts.append(pts)

        if corner_pts:
            corner_pts = np.concatenate(corner_pts, axis=0)
            ax.scatter(
                corner_pts[:, 1], corner_pts[:, 0], s=10, c="gold", marker="D", zorder=6,
                label="wall corner (cross-check)",
            )
            any_junction_marker = True

        if disagree_corner_pts:
            disagree_corner_pts = np.concatenate(disagree_corner_pts, axis=0)
            ax.scatter(
                disagree_corner_pts[:, 1], disagree_corner_pts[:, 0], s=24, c="gold", marker="D",
                edgecolors="red", linewidths=1.2, zorder=8,
                label="wall corner (DISAGREES with tangent-fit)",
            )
            # Ring the junction vertex itself so disagreement is visible
            # even when the small corner markers are hard to spot.
            disagree_vertices = np.array(
                [jc.coord for jc, cc in zip(junction_result.classifications, corner_cross_check)
                 if cc.agrees_with_tangent_fit is False]
            ) * scale
            ax.scatter(
                disagree_vertices[:, 1], disagree_vertices[:, 0], s=90, facecolors="none",
                edgecolors="red", linewidths=1.5, zorder=8,
            )
            any_junction_marker = True

    if kink_result is not None and len(kink_result.kinks) > 0:
        kink_pts = np.array([k.coord for k in kink_result.kinks]) * scale
        ax.scatter(
            kink_pts[:, 1], kink_pts[:, 0], s=20, c="magenta", marker="*", zorder=6,
            label="kink (suspected 2 cracks, not split)",
        )
        any_junction_marker = True

    ax.set_xlim(0, disp_w)
    ax.set_ylim(disp_h, 0)
    ax.axis("off")
    if any_junction_marker:
        # Below the axes, not on top of the image -- see module docstring.
        ax.legend(
            loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=3,
            fontsize=6, markerscale=1.3, framealpha=0.9,
        )

    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return scale
