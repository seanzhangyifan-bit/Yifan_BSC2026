"""Rose-histogram checks on synthetic oriented-segment fields with known
direction distributions. Tolerances come from 8 random seeds per field
(2026-11-13): measured ranges are in each test's comment.
"""

import numpy as np

from src.crackgraph.anisotropy import compute_anisotropy, share_near
from src.crackgraph.binarize import binarize
from src.crackgraph.graph import extract_graph
from src.crackgraph.skeleton import skeletonize_and_prune
from src.crackgraph.synthetic import generate_oriented_segment_field

ALIGNED_SHARE_MIN = 0.75  # measured 0.82-0.95
RANDOM_MAX_BIN_SHARE = 0.2  # measured 0.08-0.15; the aligned field gives >= 0.45
GRID_FAMILY_SHARE_MIN = 0.25  # measured >= 0.30 per family
UNEQUAL_GRID_MARGIN = 0.2  # near 0 minus near 90, measured >= 0.29


def _run(**kwargs):
    gray = generate_oriented_segment_field(**kwargs)
    binarize_result = binarize(gray)
    skeleton_result = skeletonize_and_prune(binarize_result.mask, source_image=gray, spur_px=3)
    return compute_anisotropy(skeleton_result.skeleton, extract_graph(skeleton_result.skeleton))


def test_single_direction_field_concentrates_near_that_direction():
    result = _run(bearings_deg=[0.0], n_segments=60, rng_seed=1)
    assert share_near(result, 0.0) > ALIGNED_SHARE_MIN


def test_uniform_random_field_has_no_dominant_bin():
    result = _run(bearings_deg=None, n_segments=60, rng_seed=2)
    counts = result.histogram_weighted_counts
    assert counts.max() / counts.sum() < RANDOM_MAX_BIN_SHARE


def test_equal_weight_orthogonal_grid_shows_two_separated_peaks():
    # The case a single 2nd-order index can't tell from random directions.
    result = _run(bearings_deg=[0.0, 90.0], bearing_weights=[0.5, 0.5], n_segments=80, rng_seed=3)
    assert share_near(result, 0.0) > GRID_FAMILY_SHARE_MIN
    assert share_near(result, 90.0) > GRID_FAMILY_SHARE_MIN
    top_two = np.argsort(result.histogram_weighted_counts)[-2:]
    assert abs(int(top_two[0]) - int(top_two[1])) >= 5  # >= 50 deg apart


def test_unequal_weight_orthogonal_grid_favours_the_main_direction():
    result = _run(bearings_deg=[0.0, 90.0], bearing_weights=[0.8, 0.2], n_segments=80, rng_seed=4)
    assert share_near(result, 0.0) - share_near(result, 90.0) > UNEQUAL_GRID_MARGIN


def test_no_samples_gives_an_empty_histogram():
    from src.crackgraph.anisotropy import anisotropy_from_samples

    result = anisotropy_from_samples([])
    assert result.n_samples == 0 and result.histogram_weighted_counts.sum() == 0
    assert share_near(result, 0.0) == 0.0
