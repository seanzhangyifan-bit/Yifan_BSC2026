"""Checks for the connectivity helpers in src/crackgraph/measures/crack_stats.py
(giant component, its span, parallel segments), plus per-region width and
segment-length behaviour through measure_crack_stats. Moved from the
archived tests/test_export_crack_stats.py on 2026-11-13; the median-width
and median-length helpers those tests covered are now inside
measure_crack_stats and are tested through it below.
"""

import networkx as nx
import numpy as np
import pandas as pd
from PIL import Image

from src.crackgraph.analysis import analyze_image
from src.crackgraph.graph import extract_graph
from src.crackgraph.measures.crack_stats import (
    crack_network_graph,
    giant_component_nodes,
    giant_component_span_px,
)
from src.crackgraph.regions import RegionSpec
from src.crackgraph.settings import AnalysisSettings
from src.crackgraph.skeleton import skeletonize_and_prune


def _save(gray: np.ndarray, path):
    Image.fromarray(gray.astype(np.uint8)).convert("RGB").save(path)
    return path


def test_median_width_matches_known_band_thickness(tmp_path):
    # One straight bright band, 10 px thick: the per-pixel width should
    # recover that thickness.
    gray = np.full((220, 320), 20, np.uint8)
    gray[100:110, 10:300] = 230
    row = analyze_image(_save(gray, tmp_path / "band.png"), AnalysisSettings()).rows[0]
    assert abs(row["median_width_px"] - 10.0) < 1.5


def test_segment_counted_once_in_a_grid(tmp_path):
    # A band crossing both cells of a 1x2 grid: its length is split between
    # the cells (pixel rule), but the segment itself goes whole to one cell
    # (middle-pixel rule).
    gray = np.full((100, 400), 20, np.uint8)
    gray[45:55, 20:380] = 230
    path = _save(gray, tmp_path / "band2.png")
    rows = analyze_image(path, AnalysisSettings(
        regions=RegionSpec(mode="grid", n_rows=1, n_cols=2))).rows
    with_segment = [r for r in rows if not np.isnan(r["avg_edge_length_px"])]
    assert len(with_segment) == 1
    whole = analyze_image(path, AnalysisSettings()).rows[0]
    assert with_segment[0]["avg_edge_length_px"] == whole["avg_edge_length_px"]


def test_giant_component_nodes_picks_largest_total_length_not_largest_node_count():
    # Component {0, 1, 2} has 3 nodes but only 10px of total length;
    # component {3, 4} has 2 nodes but 100px of total length -- the giant
    # component must be chosen by summed edge length, matching
    # giant_component_fraction's own definition, not by node count.
    G = nx.Graph()
    G.add_edge(0, 1, branch_distance=5.0)
    G.add_edge(1, 2, branch_distance=5.0)
    G.add_edge(3, 4, branch_distance=100.0)
    assert giant_component_nodes(G) == {3, 4}


def test_giant_component_nodes_empty_graph_returns_empty_set():
    assert giant_component_nodes(nx.Graph()) == set()


def test_giant_component_span_matches_known_diagonal():
    coords = np.array([[0, 0], [0, 100], [100, 0], [100, 100], [50, 50]])
    span = giant_component_span_px(coords)
    assert abs(span - float(np.hypot(100, 100))) < 1e-6


def test_giant_component_span_handles_collinear_points():
    # A straight-line component (e.g. one isolated crack) is a degenerate
    # convex hull -- scipy's ConvexHull raises on exactly-collinear input,
    # so this must fall back to brute force rather than propagate that
    # error.
    coords = np.array([[0, 0], [0, 10], [0, 20], [0, 30]])
    span = giant_component_span_px(coords)
    assert abs(span - 30.0) < 1e-6


def test_giant_component_span_fewer_than_two_nodes_returns_nan():
    assert np.isnan(giant_component_span_px(np.zeros((1, 2))))
    assert np.isnan(giant_component_span_px(np.zeros((0, 2))))

def test_giant_component_span_handles_a_closed_loop_with_no_junctions():
    # A rectangular ring (constant band width, hollowed-out middle) is
    # topologically a simple closed curve -- no junctions anywhere along it,
    # since every skeleton pixel has degree 2. skan still needs one node id
    # to anchor the loop in its graph representation, so this produces
    # exactly one node with a self-loop edge -- the same topology observed
    # on the real T5-PTFE_H50_v2 image, whose giant component turned out to
    # be exactly this shape. A node-coordinate-only span is undefined for a
    # single point; the fix (this test) is to build the span from the
    # self-loop edge's own full pixel path instead, which does have real
    # spatial extent.
    mask = np.zeros((160, 220), dtype=bool)
    mask[20:140, 20:200] = True
    mask[35:125, 35:185] = False

    result = skeletonize_and_prune(mask, spur_px=3)
    graph_result = extract_graph(result.skeleton)
    summary = graph_result.summary
    G = nx.from_pandas_edgelist(
        summary, source="node_id_src", target="node_id_dst", edge_attr="branch_distance"
    )
    gc_nodes = giant_component_nodes(G)
    assert gc_nodes == {0}, "expected the single self-loop node, confirming the topology this test targets"

    # Old (broken) approach: node coordinates only -- one point, span is NaN.
    node_id_to_coord = dict(zip(graph_result.node_ids.tolist(), graph_result.node_coords))
    old_coords = np.array([node_id_to_coord[n] for n in gc_nodes])
    assert np.isnan(giant_component_span_px(old_coords))

    # New (fixed) approach: full pixel path of every edge inside the giant component.
    gc_edge_mask = summary["node_id_src"].isin(gc_nodes) & summary["node_id_dst"].isin(gc_nodes)
    new_coords = np.concatenate([
        result.skeleton.path_coordinates(int(idx)) for idx in summary.index[gc_edge_mask]
    ])
    span = giant_component_span_px(new_coords)

    # The ring's outer footprint is 120 rows x 180 cols, its medial-axis loop
    # sits inset by half the ~15px band width on each side -- the diagonal
    # of that loop should be in the right ballpark, well clear of both 0
    # and NaN.
    assert not np.isnan(span)
    assert 150 < span < 220


def test_crack_network_graph_keeps_parallel_segments():
    # Two different segments join junctions 1 and 2 (the two sides of a small
    # cell), plus a separate short piece. A plain nx.Graph keeps only one of
    # the parallel pair, so the giant component's length came out short.
    summary = pd.DataFrame({
        "node_id_src": [1, 1, 2, 7],
        "node_id_dst": [2, 2, 3, 8],
        "branch_distance": [40.0, 50.0, 10.0, 5.0],
    })
    G = crack_network_graph(summary)
    gc = giant_component_nodes(G)
    assert gc == {1, 2, 3}
    gc_length = sum(d["branch_distance"] for *_, d in G.subgraph(gc).edges(data=True))
    assert gc_length == 100.0
