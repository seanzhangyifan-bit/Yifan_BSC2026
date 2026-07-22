"""Correctness checks for stage 2 pruning, in particular the
correlation-based corner-tracing-artifact criterion: a synthetic wedge
(width ramps monotonically from a free tip to a T-junction, mimicking a
medial-axis branch tracing into a concave mask-boundary corner) must be
pruned when the criterion is enabled and survive when it's disabled; a
genuine constant-width line must never be flagged.
"""

import numpy as np
from skimage.draw import polygon

from src.crackgraph.skeleton import HOLE_AREA_THRESHOLD_PX2, is_corner_tracing_artifact, skeletonize_and_prune

import skan


def _wedge_artifact_mask(size: int = 260) -> np.ndarray:
    """A long, constant-width horizontal host line (two ~120px arms either
    side of a T-junction) with a triangular wedge fused to its underside:
    base (width 30px) coincides with the host, apex is a free point ~60px
    below. Skeletonizing this yields a T-junction with one arm (the wedge)
    whose width ramps from ~0 at the free tip up to host width at the
    junction -- the same shape as the real corner-tracing artifact this
    criterion was designed against (see skeleton.py module docstring), not
    a literal concave-corner mask. The host arms are made long relative to
    the junction-blob region so their own near-junction width bump (a real,
    separate effect -- junction blobs are locally wider than their arms)
    stays a small fraction of each arm's profile and doesn't itself trend
    with correlation > CORR_THRESHOLD: measured directly, host-arm
    correlation ~0.48 vs. wedge correlation ~0.99 at these proportions."""
    mask = np.zeros((size, size), dtype=bool)
    mask[120:127, 10:250] = True
    rr, cc = polygon(np.array([127, 127, 190]), np.array([115, 145, 130]), shape=mask.shape)
    mask[rr, cc] = True
    return mask


def _has_branch_near_length(skel: skan.Skeleton, branch_type: int, length: float, tol: float) -> bool:
    summary = skan.summarize(skel, separator="_")
    if len(summary) == 0:
        return False
    matches = summary[summary["branch_type"] == branch_type]
    return bool((abs(matches["branch_distance"] - length) < tol).any())


def test_ramp_is_flagged_as_corner_artifact():
    widths = np.linspace(2.0, 40.0, 30)
    assert is_corner_tracing_artifact(widths, corr_threshold=0.99) is True


def test_flat_noisy_width_is_not_flagged():
    rng = np.random.default_rng(0)
    widths = 6.0 + rng.normal(0.0, 0.3, size=30)
    assert is_corner_tracing_artifact(widths, corr_threshold=0.99) is False


def test_short_branch_is_never_flagged_regardless_of_shape():
    # A perfect ramp, but shorter than MIN_LEN_FOR_CORR_PX -- no data, no
    # constraint, per CLAUDE.md's near-120-deg-junction precedent.
    widths = np.array([2.0, 40.0])
    assert is_corner_tracing_artifact(widths, corr_threshold=0.99, min_len_px=4) is False


def test_wedge_pruned_when_criterion_enabled():
    mask = _wedge_artifact_mask()
    # Uses the real production default (CORR_THRESHOLD=0.99), not a
    # test-loosened value -- the mask was sized so the wedge (~0.99
    # correlation) clears it while the host arms (~0.48) stay well under.
    result = skeletonize_and_prune(mask, spur_px=3, corner_artifact_corr_threshold=0.99)
    assert result.n_corner_artifacts_pruned >= 1
    assert not _has_branch_near_length(result.skeleton, branch_type=1, length=60.0, tol=10.0)

    corner_records = [b for b in result.pruned_branches if b.reason == "corner_artifact"]
    assert len(corner_records) == 1
    record = corner_records[0]
    assert abs(record.branch_distance - 60.0) < 10.0
    assert record.coords.shape[1] == 2
    assert len(record.coords) > 1


def test_wedge_survives_when_criterion_disabled():
    mask = _wedge_artifact_mask()
    result = skeletonize_and_prune(mask, spur_px=3, corner_artifact_corr_threshold=None)
    assert result.n_corner_artifacts_pruned == 0
    assert _has_branch_near_length(result.skeleton, branch_type=1, length=60.0, tol=10.0)
    assert [b for b in result.pruned_branches if b.reason == "corner_artifact"] == []


def test_constant_width_line_is_never_flagged_as_corner_artifact():
    mask = np.zeros((260, 260), dtype=bool)
    mask[120:127, 10:250] = True  # straight line only, no wedge
    result = skeletonize_and_prune(mask, spur_px=3, corner_artifact_corr_threshold=0.8)
    assert result.n_corner_artifacts_pruned == 0


def test_small_enclosed_hole_is_filled_before_skeletonize():
    # A crack-like band (not a filled blob -- skeletonize_and_prune on a
    # solid block degenerately prunes to nothing) with a tiny fully-
    # enclosed background hole well below HOLE_AREA_THRESHOLD_PX2 -- should
    # be filled by remove_small_holes before skeletonize() ever sees it,
    # per the user's own observation that small black specks were
    # surviving into the real pass untouched.
    mask = np.zeros((100, 200), dtype=bool)
    mask[40:60, 10:190] = True  # 20px-thick horizontal band
    hole_side = 5  # 25 px^2, well under the 50 px^2 threshold
    assert hole_side * hole_side < HOLE_AREA_THRESHOLD_PX2
    mask[47:47 + hole_side, 95:95 + hole_side] = False

    result = skeletonize_and_prune(mask, spur_px=3)
    assert result.mask_clean[47:47 + hole_side, 95:95 + hole_side].all()


def test_large_enclosed_hole_is_not_filled():
    # A hole above the threshold must survive -- filling has to be
    # size-gated, not unconditional.
    mask = np.zeros((100, 200), dtype=bool)
    mask[30:70, 10:190] = True  # 40px-thick band, wide enough to enclose the hole
    hole_side = 12  # 144 px^2, well over the 50 px^2 threshold
    assert hole_side * hole_side > HOLE_AREA_THRESHOLD_PX2
    mask[44:44 + hole_side, 95:95 + hole_side] = False

    result = skeletonize_and_prune(mask, spur_px=3)
    assert not result.mask_clean[44:44 + hole_side, 95:95 + hole_side].any()
