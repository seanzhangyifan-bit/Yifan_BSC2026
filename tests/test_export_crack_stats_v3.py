"""Correctness checks for crack_stats_v3's two departures from
scripts/export_crack_stats.py (v1): flaking.flake_touching_path_indices
(omit-by-membership, no distance buffer) and building the connectivity
graph from the OMITTED-filtered edge set rather than the full summary.
See docs/crack_stats_v3_status.md for the full methodology writeup this
is validating.
"""

from types import SimpleNamespace

import networkx as nx
import numpy as np
import pandas as pd

from src.crackgraph.flaking import exclude_flaking_regions, flake_touching_path_indices
from src.crackgraph.graph import extract_graph
from src.crackgraph.skeleton import skeletonize_and_prune


def test_flake_touching_flags_edge_with_a_pixel_inside_excluded_mask():
    # Single straight band, no junction -- one edge end to end (an
    # "isolated fragment" in skan's branch_type terms, long enough to
    # survive spur_px=3 pruning).
    mask = np.zeros((200, 320), dtype=bool)
    mask[100:110, 10:300] = True

    result = skeletonize_and_prune(mask, spur_px=3)
    graph_result = extract_graph(result.skeleton)
    assert len(graph_result.summary) == 1

    excluded_mask = np.zeros(mask.shape, dtype=bool)
    excluded_mask[100:110, 150:170] = True  # overlaps the middle of the path

    flagged = flake_touching_path_indices(result.skeleton, graph_result, excluded_mask)
    assert flagged == set(graph_result.summary.index)


def test_flake_touching_returns_empty_set_when_mask_is_empty():
    mask = np.zeros((200, 320), dtype=bool)
    mask[100:110, 10:300] = True

    result = skeletonize_and_prune(mask, spur_px=3)
    graph_result = extract_graph(result.skeleton)

    excluded_mask = np.zeros(mask.shape, dtype=bool)
    assert flake_touching_path_indices(result.skeleton, graph_result, excluded_mask) == set()


def test_flake_touching_ignores_edge_that_never_enters_excluded_mask():
    mask = np.zeros((200, 320), dtype=bool)
    mask[100:110, 10:300] = True

    result = skeletonize_and_prune(mask, spur_px=3)
    graph_result = extract_graph(result.skeleton)

    # Far from the skeleton path (row 100-110) -- must not flag anything.
    excluded_mask = np.zeros(mask.shape, dtype=bool)
    excluded_mask[0:10, 0:10] = True

    assert flake_touching_path_indices(result.skeleton, graph_result, excluded_mask) == set()


def test_no_edges_returns_empty_set():
    empty_summary = pd.DataFrame({"node_id_src": [], "node_id_dst": [], "branch_distance": []})
    fake_graph_result = SimpleNamespace(summary=empty_summary)

    excluded_mask = np.ones((10, 10), dtype=bool)
    assert flake_touching_path_indices(None, fake_graph_result, excluded_mask) == set()


def test_omitting_flake_touching_edges_keeps_two_real_networks_separate():
    # Two real crack-like networks (each an 8px-tall band with its own
    # T-branch stub, so each has real junction structure independent of the
    # blob) that would only be connected to each other via a large, wide
    # blob standing in for a flaked/delaminated patch -- no other path
    # between them. Physically, the raw mask IS one connected region (the
    # blob bridges the gap), so its own skeleton is connected too --
    # building the connectivity graph from the FULL, unfiltered summary
    # must show ONE component, which is exactly the false-bridging failure
    # mode this pipeline exists to avoid. Filtering by
    # flake_touching_path_indices's output must split it back into two
    # components, one per real network, since each one's T-branch survives
    # entirely outside the excluded region even after the single edge
    # running into the blob is dropped.
    mask = np.zeros((260, 500), dtype=bool)
    band_rows = slice(120, 128)  # 8px-tall real cracks
    mask[band_rows, 20:180] = True     # band A
    mask[128:158, 96:104] = True       # T-stub off band A, well clear of the blob
    mask[60:190, 180:260] = True       # blob (130 tall x 80 wide, >> 4x band width)
    mask[band_rows, 260:420] = True    # band B
    mask[128:158, 336:344] = True      # T-stub off band B, well clear of the blob

    result = skeletonize_and_prune(mask)
    graph_result = extract_graph(result.skeleton)
    summary = graph_result.summary

    flaking_result = exclude_flaking_regions(
        result.mask_clean, result.skel_image, result.medial_radius,
    )
    assert flaking_result.candidates, "expected the blob to be identified as a flaking candidate"

    omitted = flake_touching_path_indices(
        result.skeleton, graph_result, flaking_result.excluded_mask,
    )
    assert omitted, "expected at least one edge touching the excluded blob"

    G_unfiltered = nx.from_pandas_edgelist(
        summary, source="node_id_src", target="node_id_dst", edge_attr="branch_distance",
    )
    assert nx.number_connected_components(G_unfiltered) == 1, (
        "sanity check: the two networks must appear falsely connected without filtering"
    )

    kept_summary = summary.loc[~summary.index.isin(omitted)]
    G_filtered = nx.from_pandas_edgelist(
        kept_summary, source="node_id_src", target="node_id_dst", edge_attr="branch_distance",
    )
    components = list(nx.connected_components(G_filtered))
    assert len(components) == 2, (
        "omitting flake-touching edges must separate the two real crack networks"
    )
    assert {len(c) for c in components} == {3, 3}, (
        "each surviving network is its own T-branch (junction + 2 tips), untouched by the blob"
    )
