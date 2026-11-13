"""Crack statistics for one region: area, width, segment length,
connectivity, flaking and pruning counts. Column reference:
docs/batch_stats/crack_stats_schema.md.

How a region is cut from the one whole-image result:
- Pixel quantities (crack area, flaked area, per-pixel width, total crack
  length) count only the pixels inside the region, so grid cells add up to
  the whole image.
- Segment quantities (segment length, pruned-branch counts) take each
  segment whole and give it to the region holding its middle pixel, so a
  segment cut by a cell border isn't counted as two short ones.
- Connectivity is measured on the whole image only. Cutting the network at
  a region border splits it into more, smaller pieces, so a region's
  connectivity would mostly reflect the region's size, not the cracking.
For the whole image these rules give the same numbers as before 2026-11-13.
"""

import networkx as nx
import numpy as np
import pandas as pd
from scipy.spatial import ConvexHull
from scipy.spatial.distance import pdist

from src.crackgraph.engine import EngineResult
from src.crackgraph.regions import Region
from src.crackgraph.settings import AnalysisSettings


def crack_network_graph(summary: pd.DataFrame) -> nx.MultiGraph:
    """Junction/endpoint nodes joined by one graph edge per skeleton segment.

    A MultiGraph, not a Graph: two different segments can join the same pair
    of junctions (the two sides of a small cell). A plain Graph keeps only one
    of them, so the giant component's length came out short while the total
    length counted both, biasing giant_component_fraction low (by up to 0.007
    on the images checked, 2026-11-11)."""
    return nx.from_pandas_edgelist(
        summary, source="node_id_src", target="node_id_dst",
        edge_attr="branch_distance", create_using=nx.MultiGraph,
    )


def giant_component_nodes(G: nx.Graph) -> set:
    """Node ids of the connected component with the largest total skeleton
    length (summed edge length, not node count)."""
    components = list(nx.connected_components(G))
    if not components:
        return set()
    lengths = [
        sum(d["branch_distance"] for _, _, d in G.subgraph(c).edges(data=True))
        for c in components
    ]
    return components[int(np.argmax(lengths))]


def giant_component_span_px(points: np.ndarray) -> float:
    """Straight-line distance (px) between the two farthest-apart points
    (row, col pairs). The farthest pair always lies on the convex hull, so
    only hull points are compared; falls back to all points when the hull
    is degenerate (all points on one line)."""
    if len(points) < 2:
        return float("nan")
    pts = points
    if len(points) > 3:
        try:
            pts = points[ConvexHull(points).vertices]
        except Exception:
            pts = points
    d = pdist(pts)
    return float(d.max()) if len(d) > 0 else float("nan")


def _median_or_nan(values) -> float:
    return float(np.median(values)) if len(values) > 0 else float("nan")


def _length_inside_px(engine: EngineResult, path_index: int, branch_distance: float, region: Region) -> float:
    """Length of one segment that lies inside the region: the whole
    branch_distance if every pixel is inside, otherwise the summed steps
    between consecutive pixels that are both inside."""
    rr, cc = engine.path_pixels(path_index)
    inside = region.contains(rr, cc)
    if inside.all():
        return branch_distance
    if not inside.any():
        return 0.0
    coords = engine.skeleton.skeleton.path_coordinates(int(path_index))
    steps = np.linalg.norm(np.diff(coords, axis=0), axis=1)
    return float(steps[inside[:-1] & inside[1:]].sum())


def measure_crack_stats(engine: EngineResult, region: Region, settings: AnalysisSettings) -> dict:
    groups = set(settings.crack_stats_groups)
    um = settings.um_per_px
    summary = engine.graph.summary
    rs, cs = region.row_slice, region.col_slice
    medial_radius = engine.skeleton.medial_radius

    kept = engine.kept_paths
    # Segments whose middle pixel is in this region (see module docstring).
    assigned = [p for p in kept if region.contains_point(*engine.path_midpoint(p))]
    assigned_summary = summary.loc[assigned]

    crack_area_px2 = float(engine.flaking.mask_corrected[rs, cs].sum())
    excluded_px = int(engine.flaking.excluded_mask[rs, cs].sum())
    total_length_px = sum(
        _length_inside_px(engine, p, float(summary.at[p, "branch_distance"]), region) for p in kept
    )

    row = {}
    if "area" in groups:
        valid_area_px2 = region.area_px - excluded_px
        row["crack_area_pct"] = 100.0 * crack_area_px2 / region.area_px
        # Divides by the area we have evidence about: the region minus the
        # flaked part, which could be cracked or not underneath.
        row["crack_area_pct_excl_flakes"] = (
            100.0 * crack_area_px2 / valid_area_px2 if valid_area_px2 > 0 else float("nan")
        )
        row["crack_area_mm2"] = crack_area_px2 * um**2 / 1e6

    if "width" in groups:
        avg_width_px = crack_area_px2 / total_length_px if total_length_px > 0 else float("nan")
        widths = []
        for p in kept:
            rr, cc = engine.path_pixels(p)
            inside = region.contains(rr, cc)
            widths.append(2.0 * medial_radius[rr[inside], cc[inside]])
        median_width_px = _median_or_nan(np.concatenate(widths) if widths else [])
        row["avg_width_px"] = avg_width_px
        row["avg_width_um"] = avg_width_px * um
        row["median_width_px"] = median_width_px
        row["median_width_um"] = median_width_px * um

    if "segment_length" in groups:
        lengths = assigned_summary["branch_distance"]
        avg_px = float(lengths.mean()) if len(lengths) else float("nan")
        median_px = _median_or_nan(lengths)
        row["avg_edge_length_px"] = avg_px
        row["avg_edge_length_um"] = avg_px * um
        row["median_edge_length_px"] = median_px
        row["median_edge_length_um"] = median_px * um

    if "connectivity" in groups and region.is_whole_image(engine.shape):
        G = crack_network_graph(assigned_summary)
        n_components = nx.number_connected_components(G)
        assigned_length_px = float(assigned_summary["branch_distance"].sum())
        gc_nodes = giant_component_nodes(G)
        gc_mask = (
            assigned_summary["node_id_src"].isin(gc_nodes) & assigned_summary["node_id_dst"].isin(gc_nodes)
        )
        gc_lengths = assigned_summary.loc[gc_mask, "branch_distance"]
        if n_components > 0 and assigned_length_px > 0 and gc_nodes:
            gc_fraction = float(gc_lengths.sum()) / assigned_length_px
        else:
            gc_fraction = float("nan")
        median_gc_px = _median_or_nan(gc_lengths)
        # Span from every pixel of the giant component's segments, not just
        # its nodes: a single closed loop has one node.
        gc_points = []
        for p in assigned_summary.index[gc_mask]:
            rr, cc = engine.path_pixels(int(p))
            inside = region.contains(rr, cc)
            gc_points.append(np.column_stack([rr[inside], cc[inside]]))
        gc_points = np.concatenate(gc_points) if gc_points else np.zeros((0, 2))
        span_px = giant_component_span_px(gc_points.astype(float))
        row["n_components"] = n_components
        row["giant_component_fraction"] = gc_fraction
        row["median_edge_length_gc_px"] = median_gc_px
        row["median_edge_length_gc_um"] = median_gc_px * um
        row["giant_component_span_px"] = span_px
        row["giant_component_span_um"] = span_px * um

    if "flaking" in groups:
        row["flaking_excluded_area_pct"] = 100.0 * excluded_px / region.area_px
        row["flaking_n_candidates"] = sum(
            1 for c in engine.flaking.candidates
            if region.contains_point((c.bbox[0] + c.bbox[2]) / 2, (c.bbox[1] + c.bbox[3]) / 2)
        )
        row["flaking_n_edges_omitted"] = sum(
            1 for p in engine.omitted if region.contains_point(*engine.path_midpoint(p))
        )

    if "pruning" in groups:
        n = 0
        for b in engine.skeleton.pruned_branches:
            if b.reason != "host_stub":
                continue
            r, c = b.coords[len(b.coords) // 2]
            n += region.contains_point(r, c)
        row["n_host_stubs_pruned"] = n

    return row
