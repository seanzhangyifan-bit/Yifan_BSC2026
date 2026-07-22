"""Correctness checks for the per-pixel median-width helper added on top of
scripts/export_crack_stats.py's existing area/length avg_width_px -- see
docs/crack_stats_schema.md section 4 and the module docstring on
median_pixelwise_width_px for why this exists alongside, not instead of,
the older ratio-based estimate. Also covers the thesis-notation additions
(median_edge_length_px, giant_component_nodes, giant_component_span_px)
added for the ledge / ledge_gc / dgc statistics -- see
docs/crack_stats_v2_status.md for what prompted them.
"""

import networkx as nx
import numpy as np
import pandas as pd
from scipy.ndimage import distance_transform_edt

from scripts.export_crack_stats import (
    giant_component_nodes,
    giant_component_span_px,
    median_edge_length_px,
    median_pixelwise_width_px,
)
from src.crackgraph.graph import extract_graph
from src.crackgraph.skeleton import skeletonize_and_prune



def test_median_width_matches_known_band_thickness():
    # A single straight band, constant 10px thickness, long enough that
    # skeletonization settles into one clean centerline. No junction, so
    # this is purely a check that the per-pixel EDT sampling recovers the
    # mask's own known width.
    mask = np.zeros((220, 320), dtype=bool)
    mask[100:110, 10:300] = True

    result = skeletonize_and_prune(mask, spur_px=3)
    graph_result = extract_graph(result.skeleton)
    medial_radius = distance_transform_edt(result.mask_clean)

    median_width_px = median_pixelwise_width_px(
        result.skeleton, graph_result, cut_adjacent=set(), medial_radius=medial_radius
    )
    assert abs(median_width_px - 10.0) < 1.5


def test_cut_adjacent_exclusion_drops_the_flagged_edge():
    # A short, thin host line (8px) feeding into a much longer, much wider
    # stub (40px) at a T-junction -- the stub's own path pixels dominate
    # the total pixel count, so an unfiltered median reads the stub's
    # width. Excluding the stub's own path index from cut_adjacent (the
    # same exclusion set cut_adjacent_path_indices would produce for a
    # real flaking-boundary cut) must pull the median back down to the
    # host's own width.
    mask = np.zeros((350, 200), dtype=bool)
    mask[100:108, 10:110] = True  # host, width 8
    mask[108:300, 50:90] = True  # stub, width 40, dominates total pixel count

    result = skeletonize_and_prune(mask, spur_px=3)
    graph_result = extract_graph(result.skeleton)
    medial_radius = distance_transform_edt(result.mask_clean)

    # Host arms' own paths run up to the shared junction node (row ~119);
    # only the true stub path continues well past it, so a threshold
    # comfortably above the junction row isolates just the stub edge.
    stub_indices = set()
    for path_index in graph_result.summary.index:
        coords = result.skeleton.path_coordinates(int(path_index))
        if (coords[:, 0] > 150).any():
            stub_indices.add(int(path_index))
    assert len(stub_indices) == 1, "expected exactly one edge running into the stub"

    median_with_stub = median_pixelwise_width_px(
        result.skeleton, graph_result, cut_adjacent=set(), medial_radius=medial_radius
    )
    median_without_stub = median_pixelwise_width_px(
        result.skeleton, graph_result, cut_adjacent=stub_indices, medial_radius=medial_radius
    )

    assert abs(median_with_stub - 40.0) < 1.5
    assert abs(median_without_stub - 8.0) < 1.5


def test_no_edges_returns_nan():
    # Isolates median_pixelwise_width_px's own empty-summary branch
    # directly, rather than going through skan.Skeleton on an all-background
    # mask -- skan's own sparse-matrix construction cannot represent a
    # completely empty skeleton (a separate, pre-existing limitation, not
    # something this helper should route around).
    class _EmptySummary:
        index = pd.Index([], dtype=int)

    class _FakeGraphResult:
        summary = _EmptySummary()

    median_width_px = median_pixelwise_width_px(
        skel=None, graph_result=_FakeGraphResult(), cut_adjacent=set(),
        medial_radius=np.zeros((10, 10)),
    )
    assert np.isnan(median_width_px)


def test_median_edge_length_is_median_not_mean():
    # [10, 10, 100, 5] -- mean is 31.25, median is 10; using median must NOT
    # match avg_edge_length_px's mean-based value.
    summary = pd.DataFrame({
        "node_id_src": [0, 1, 2, 3],
        "node_id_dst": [1, 2, 3, 4],
        "branch_distance": [10.0, 10.0, 100.0, 5.0],
    })
    assert median_edge_length_px(summary, cut_adjacent=set()) == 10.0


def test_median_edge_length_excludes_cut_adjacent():
    summary = pd.DataFrame({
        "node_id_src": [0, 1, 2, 3],
        "node_id_dst": [1, 2, 3, 4],
        "branch_distance": [10.0, 10.0, 100.0, 5.0],
    })
    # Drop the 100.0 outlier (as if it were flagged cut-adjacent) -- median
    # of the remaining [10, 10, 5] is 10.
    result = median_edge_length_px(summary, cut_adjacent={2})
    assert result == 10.0


def test_median_edge_length_node_filter_isolates_giant_component():
    summary = pd.DataFrame({
        "node_id_src": [0, 1, 2, 3],
        "node_id_dst": [1, 2, 3, 4],
        "branch_distance": [10.0, 10.0, 100.0, 5.0],
    })
    # Edges 0 (0-1) and 1 (1-2) have both endpoints in {0, 1, 2}; edges 2
    # and 3 each touch a node outside the filter and must be dropped.
    result = median_edge_length_px(summary, cut_adjacent=set(), node_filter={0, 1, 2})
    assert result == 10.0


def test_median_edge_length_no_matching_edges_returns_nan():
    summary = pd.DataFrame({
        "node_id_src": [0],
        "node_id_dst": [1],
        "branch_distance": [10.0],
    })
    assert np.isnan(median_edge_length_px(summary, cut_adjacent={0}))


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
