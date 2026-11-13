"""The opt-in per-segment table: one row per kept crack segment.

Each segment is listed under the region holding its middle pixel, with its
full length (not cut at the region border).
"""

import numpy as np

from src.crackgraph.edge_metrics import estimate_edge_area_ribbon
from src.crackgraph.engine import EngineResult
from src.crackgraph.regions import Region
from src.crackgraph.settings import AnalysisSettings


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
        # [interpreted] width integrated along the centre line; runs a little
        # high where the segment passes through a wide junction.
        area_px2 = estimate_edge_area_ribbon(engine.skeleton.skeleton, p, medial_radius)
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
