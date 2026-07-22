"""Round-trip check for the analysis cache: save_analysis_cache ->
load_analysis_cache must reproduce arrays and pruned_branches exactly
(dtype, shape, values), not just approximately -- this cache exists so a
later session can trust it as a stand-in for re-running analysis.
"""

import numpy as np

from src.crackgraph.cache_io import load_analysis_cache, save_analysis_cache
from src.crackgraph.flaking import FlakingCandidate, FlakingResult
from src.crackgraph.skeleton import PrunedBranchRecord, SkeletonResult


def _make_skeleton_result(pruned_branches):
    skel_image = np.zeros((20, 20), dtype=bool)
    skel_image[5, :] = True
    return SkeletonResult(
        skeleton=None,
        skel_image=skel_image,
        mask_clean=skel_image,
        medial_radius=np.zeros((20, 20)),
        n_pixels_pre_prune=20,
        n_pixels_post_prune=20,
        n_spurs_pruned=0,
        pruned_spur_lengths=[],
        n_fragments_pruned=0,
        pruned_fragment_lengths=[],
        spur_px_threshold=15.0,
        n_corner_artifacts_pruned=sum(1 for b in pruned_branches if b.reason == "corner_artifact"),
        pruned_corner_artifact_lengths=[
            b.branch_distance for b in pruned_branches if b.reason == "corner_artifact"
        ],
        corner_artifact_corr_threshold=0.99,
        pruned_branches=pruned_branches,
        iters_used=1,
    )


def _make_flaking_result(mask_corrected, excluded_mask):
    candidates = [
        FlakingCandidate(label=1, area_px2=600, solidity=0.9, bbox=(0, 0, 10, 10)),
        FlakingCandidate(label=2, area_px2=800, solidity=0.7, bbox=(5, 5, 15, 15)),
    ]
    return FlakingResult(
        candidates=candidates,
        reference_width_px=4.5,
        excluded_mask=excluded_mask,
        mask_corrected=mask_corrected,
        excluded_area_px2=int(excluded_mask.sum()),
        excluded_area_pct=100.0 * excluded_mask.sum() / excluded_mask.size,
    )


def test_round_trip_preserves_arrays_and_pruned_branches(tmp_path):
    pruned_branches = [
        PrunedBranchRecord(reason="spur", branch_distance=8.0, coords=np.array([[1.0, 1.0], [1.0, 2.0]])),
        PrunedBranchRecord(
            reason="corner_artifact",
            branch_distance=42.5,
            coords=np.array([[3.0, 3.0], [4.0, 4.0], [5.0, 5.0]]),
        ),
    ]
    mask_corrected = np.zeros((20, 20), dtype=bool)
    mask_corrected[5, :] = True
    excluded_mask = np.zeros((20, 20), dtype=bool)
    excluded_mask[0:3, 0:3] = True

    skeleton_result = _make_skeleton_result(pruned_branches)
    flaking_result = _make_flaking_result(mask_corrected, excluded_mask)
    stats_row = {"image_filename": "fake.jpg", "crack_area_pct": 12.34, "n_components": 3}

    save_analysis_cache(
        tmp_path, "fake_image",
        skeleton_result=skeleton_result, flaking_result=flaking_result, stats_row=stats_row,
    )
    loaded = load_analysis_cache(tmp_path, "fake_image")

    assert loaded.stats_row == stats_row
    np.testing.assert_array_equal(loaded.mask_corrected, mask_corrected)
    np.testing.assert_array_equal(loaded.skeleton_final, skeleton_result.skel_image)
    np.testing.assert_array_equal(loaded.excluded_mask, excluded_mask)
    assert loaded.reference_width_px == flaking_result.reference_width_px
    assert loaded.excluded_area_px2 == flaking_result.excluded_area_px2
    assert loaded.excluded_area_pct == flaking_result.excluded_area_pct
    assert [(c.label, c.area_px2, c.solidity, c.bbox) for c in loaded.flaking_candidates] == [
        (c.label, c.area_px2, c.solidity, c.bbox) for c in flaking_result.candidates
    ]

    assert len(loaded.pruned_branches) == 2
    for original, restored in zip(pruned_branches, loaded.pruned_branches):
        assert restored.reason == original.reason
        assert restored.branch_distance == original.branch_distance
        np.testing.assert_array_equal(restored.coords, original.coords)


def test_round_trip_with_no_pruned_branches(tmp_path):
    skeleton_result = _make_skeleton_result([])
    mask = np.zeros((10, 10), dtype=bool)
    flaking_result = _make_flaking_result(mask, mask)
    flaking_result.candidates.clear()

    save_analysis_cache(
        tmp_path, "empty_case",
        skeleton_result=skeleton_result, flaking_result=flaking_result, stats_row={"x": 1},
    )
    loaded = load_analysis_cache(tmp_path, "empty_case")

    assert loaded.pruned_branches == []
    assert loaded.flaking_candidates == []
