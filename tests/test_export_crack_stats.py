"""Correctness checks for the per-pixel median-width helper added on top of
scripts/export_crack_stats.py's existing area/length avg_width_px -- see
docs/crack_stats_schema.md section 4 and the module docstring on
median_pixelwise_width_px for why this exists alongside, not instead of,
the older ratio-based estimate.
"""

import numpy as np
import pandas as pd
from scipy.ndimage import distance_transform_edt

from scripts.export_crack_stats import median_pixelwise_width_px
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
