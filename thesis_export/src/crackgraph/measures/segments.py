"""The opt-in per-segment table: one row per kept crack segment.

Each segment is listed under the region holding its middle pixel, with its
full length (not cut at the region border).
"""

import numpy as np

from src.crackgraph.engine import EngineResult
from src.crackgraph.regions import Region
from src.crackgraph.settings import AnalysisSettings


def ribbon_area_px2(rr: np.ndarray, cc: np.ndarray, coords: np.ndarray, medial_radius: np.ndarray) -> float:
    """Area of one segment: its width (2 x medial radius) integrated along
    its centre line, trapezoid rule. [interpreted] -- runs a little high
    where the segment passes through a wide junction."""
    if len(coords) < 2:
        return 0.0
    widths = 2.0 * medial_radius[rr, cc]
    steps = np.linalg.norm(np.diff(coords, axis=0), axis=1)
    return float(np.sum((widths[:-1] + widths[1:]) / 2.0 * steps))


def segment_rows(engine: EngineResult, region: Region, settings: AnalysisSettings) -> list[dict]:
    um = settings.um_per_px
    summary = engine.graph.summary
    medial_radius = engine.skeleton.medial_radius
    rows = []
    for p in engine.kept_paths:
        mid_r, mid_c = engine.path_midpoint(p)
        if not region.contains_point(mid_r, mid_c):
            continue
        rr, cc = engine.path_pixels(p)
        length_px = float(summary.at[p, "branch_distance"])
        width_px = float(np.median(2.0 * medial_radius[rr, cc]))
        coords = engine.skeleton.skeleton.path_coordinates(p).astype(float)
        area_px2 = ribbon_area_px2(rr, cc, coords, medial_radius)
        rows.append({
            "segment": p,
            "mid_row_px": mid_r,
            "mid_col_px": mid_c,
            "length_px": length_px,
            "length_um": length_px * um,
            "median_width_px": width_px,
            "median_width_um": width_px * um,
            "area_px2": area_px2,
            "area_um2": area_px2 * um**2,
        })
    return rows
