"""Correctness checks for stage 2 pruning, in particular the host-stub rule:
a dead end is removed if less than spur_px of its length lies outside the
crack it branches from. A stub from a wide crack's centre line into a small
bump on its wall must be removed (and survive with the rule off); a real side
crack or a long tapering wedge sticking out of its host must be kept; a plain
line has nothing to remove. Also checks the dark-speck fill.
"""

import numpy as np
from skimage.draw import polygon

from src.crackgraph.skeleton import DARK_SPECK_AREA_PX2, SPUR_PX_PLACEHOLDER, skeletonize_and_prune


def _wide_band(shape=(160, 260)) -> np.ndarray:
    """A 40 px wide horizontal crack (half-width 20 px), cols 10-250."""
    mask = np.zeros(shape, dtype=bool)
    mask[30:70, 10:250] = True
    return mask


def _band_with_bump() -> np.ndarray:
    """Wide band plus an 8 x 12 px bump on its lower wall. Thinning sends a
    ~23 px branch from the centre line into the bump, but only the bump's
    8 px lie outside the band -- under spur_px -- so it's a host stub."""
    mask = _wide_band()
    mask[70:78, 120:132] = True
    return mask


def _band_with_side_crack() -> np.ndarray:
    """Wide band plus a real 5 px wide side crack leaving its lower wall and
    running 55 px beyond it."""
    mask = _wide_band()
    mask[70:125, 128:133] = True
    return mask


def _thin_line_with_wedge(size: int = 260) -> np.ndarray:
    """A 7 px host line with a triangular wedge (base 30 px, apex ~63 px below)
    fused to its underside: a tapering branch that sticks ~60 px out of its
    host. It was the corner-artifact fixture under the old correlation test;
    under the host-stub rule it reads as a real tapering side crack and stays."""
    mask = np.zeros((size, size), dtype=bool)
    mask[120:127, 10:250] = True
    rr, cc = polygon(np.array([127, 127, 190]), np.array([115, 145, 130]), shape=mask.shape)
    mask[rr, cc] = True
    return mask


def test_stub_into_wall_bump_is_pruned():
    result = skeletonize_and_prune(_band_with_bump())
    assert result.n_host_stubs_pruned == 1
    (record,) = [b for b in result.pruned_branches if b.reason == "host_stub"]
    assert record.branch_distance >= SPUR_PX_PLACEHOLDER  # the length rule alone wouldn't catch it
    assert record.coords.shape[1] == 2 and len(record.coords) > 1
    # no skeleton left between the centre line and the bump
    assert not result.skel_image[52:80, 110:142].any()


def test_stub_into_wall_bump_survives_with_rule_off():
    result = skeletonize_and_prune(_band_with_bump(), prune_host_stubs=False)
    assert result.n_host_stubs_pruned == 0
    assert result.skel_image[52:80, 110:142].any()


def test_real_side_crack_is_kept():
    result = skeletonize_and_prune(_band_with_side_crack())
    assert result.n_host_stubs_pruned == 0
    assert result.skel_image[80:125, 120:140].any()


def test_tapering_wedge_sticking_out_of_host_is_kept():
    result = skeletonize_and_prune(_thin_line_with_wedge())
    assert result.n_host_stubs_pruned == 0
    assert result.skel_image[140:185, 120:140].any()


def test_plain_line_has_no_host_stubs():
    mask = np.zeros((260, 260), dtype=bool)
    mask[120:127, 10:250] = True
    result = skeletonize_and_prune(mask)
    assert result.n_host_stubs_pruned == 0


def test_small_dark_speck_is_filled_before_skeletonize():
    # A dark speck fully enclosed in a crack, below DARK_SPECK_AREA_PX2, must be
    # filled before skeletonize() sees it, so the skeleton doesn't loop round it.
    mask = np.zeros((100, 200), dtype=bool)
    mask[40:60, 10:190] = True  # 20px-thick horizontal band
    speck_side = 5  # 25 px^2
    assert speck_side * speck_side < DARK_SPECK_AREA_PX2
    mask[47:47 + speck_side, 95:95 + speck_side] = False

    result = skeletonize_and_prune(mask, spur_px=3)
    assert result.mask_clean[47:47 + speck_side, 95:95 + speck_side].all()


def test_large_dark_region_is_not_filled():
    # A dark region above the limit must survive -- filling is size-gated.
    mask = np.zeros((100, 200), dtype=bool)
    mask[30:70, 10:190] = True  # 40px-thick band, wide enough to enclose the region
    side = 13  # 169 px^2
    assert side * side > DARK_SPECK_AREA_PX2
    mask[44:44 + side, 95:95 + side] = False

    result = skeletonize_and_prune(mask, spur_px=3)
    assert not result.mask_clean[44:44 + side, 95:95 + side].any()
