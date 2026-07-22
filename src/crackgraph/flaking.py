"""Identify and exclude large flaked/delaminated catalyst-layer regions from
the crack mask before they contaminate crack-area, width, length, and
connectivity statistics.

Why this exists: a flaked-off patch (catalyst layer physically absent,
exposing substrate) reads as bright/foreground under the same Otsu threshold
as a real crack, but it is not a crack -- it is a 2D area of missing
material, not a 1D fracture. Left uncorrected, it (a) inflates
crack_area_pct, (b) corrupts avg_width_px/avg_edge_length_px because
skeletonizing its filled interior produces a genuinely multi-branched,
non-representative medial axis (not the "double-line loop" artifact
documented in skeleton.py -- a different mechanism: the medial axis of a
blob-shaped region is *inherently* branchy, this isn't thinning noise), and
(c) silently discards the fact that we have zero evidence about what crack
pattern, if any, existed under the now-missing material.

Identification (this module's own contribution, not reused from elsewhere):
a pixel is a candidate-blob pixel if its local width (2 * medial_radius,
the same EDT half-width skeleton.py already computes) exceeds
WIDTH_FLAG_MULTIPLIER_K times this image's own reference crack width --
sampled at skeleton centerline pixels only (the one place medial_radius
reads a genuine half-width rather than "however close this pixel happens to
be to an edge"), median rather than mean so a blob's own messy interior
skeleton (a small fraction of total skeleton mileage) can't drag the
reference value up. Connected components of the flagged region are kept as
candidates only above MIN_CANDIDATE_AREA_PX2 -- width is the single
identification criterion, deliberately: an earlier version also required
high solidity (area / convex-hull area) to separate compact blobs from
merely-locally-wide, elongated crack bands, but that second criterion was
dropped after a real elongated candidate on T2-A_membran_v2 (solidity
0.674, well below the 0.75 cutoff) was confirmed by inspection to be real
delamination, not a wide crack -- solidity was excluding genuine cases and
was harder to justify than width alone. One criterion, explainable, beats
two where the second one is doing more harm than good.

Treatment: WIDTH_FLAG_MULTIPLIER_K=4 means a flagged seed pixel is, by
construction, more than (K/2) * reference_width_px from the nearest
background pixel -- the seed starts already eroded inward from the true
boundary by that amount. Growing the seed back out has to at least undo
that erosion before it can reach the true edge; GROWTH_MULTIPLIER=2.2
follows directly (2.0 = K/2 exactly undoes the erosion, +10% margin to
reliably clear it -- verified by visual inspection against real candidates,
not derived from first principles). Growth is mask-constrained dilation
(can never cross a real black boundary), cropped to each candidate's padded
bounding box (growth is inherently local, so this is a safe, not a lossy,
optimization). Nothing here converges to a fully "moated" stop in the
mathematical sense -- almost every candidate touches at least one thin
crack corridor, and dilation will keep creeping a little further down it on
every step, forever, in a fully connected network. GROWTH_MULTIPLIER is
therefore a disclosed stopping budget, not a discovered boundary.

Deliberately not built here: any attempt to reshape the exclusion boundary
to look more like a natural crack tip (a "meniscus", considered and
rejected in favour of the approach below) -- that would be shaping the
output to look right rather than measuring anything, which this project's
own evidence-level discipline rules out. Instead, edges that end up
touching the exclusion boundary are meant to be flagged and dropped from
downstream length/width statistics (see cut_adjacent_path_indices) rather
than having their geometry cosmetically smoothed.

Every constant below is 🔴 assumed (chosen by inspection this session, no
independent sweep) except where noted -- see CALIBRATION.md's convention.
"""

from dataclasses import dataclass, field

import numpy as np
from scipy.ndimage import distance_transform_edt
from skimage.measure import label, regionprops
from skimage.morphology import binary_dilation, disk

# How many multiples of this image's own reference crack width a pixel's
# local width must exceed to be flagged as a candidate-blob pixel. Chosen
# to comfortably clear normal crack-width variance (irregular walls,
# junction blobs) while still catching genuinely oversized regions -- not
# swept. 🔴 assumed
WIDTH_FLAG_MULTIPLIER_K = 4.0

# Minimum connected-component area (px^2) of flagged pixels to consider as a
# flaking candidate at all, screening out small noise specks. 🔴 assumed
MIN_CANDIDATE_AREA_PX2 = 500

# Growth budget, in multiples of the reference crack width, for recovering
# each candidate's true boundary from its (by-construction eroded) seed.
# 2.0 = WIDTH_FLAG_MULTIPLIER_K / 2 exactly undoes the seed's own erosion;
# the extra 0.2 is a margin verified by visual inspection (this session, on
# T2-A_membran_v2) to reliably reach the true black boundary without
# growing much further than needed. 🟡 empirical, uncalibrated -- verified
# by eye on one real image, not swept.
GROWTH_MULTIPLIER = 2.2

# Dilation structuring-element radius (px) used per growth step. This is a
# resolution/speed knob, not a calibration choice -- it controls how finely
# "has growth converged yet" gets checked, not how far growth is allowed to
# go (that's GROWTH_MULTIPLIER).
GROWTH_STEP_PX = 3

# Buffer distance, in multiples of this image's own reference crack width,
# within which an edge's path is treated as "cut-adjacent" and dropped from
# length/width statistics -- see cut_adjacent_path_indices. A flat pixel
# value (originally 10px) was tried first and measured too small: on
# T2-A_membran_v2 it flagged only 46 edges and visibly missed most of the
# boundary perimeter, while 1.0x reference width flagged 86 and covered the
# whole perimeter. 🟡 empirical -- verified by inspection on one real image,
# not swept.
CUT_ADJACENT_BUFFER_WIDTH_MULTIPLIER = 1.0


@dataclass
class FlakingCandidate:
    label: int
    area_px2: int  # [measured]
    solidity: float  # [measured] area / convex-hull area -- reported for diagnostic
    # visibility only, NOT a filter criterion (see module docstring for why
    # solidity was dropped as a pass/fail gate).
    bbox: tuple[int, int, int, int]  # (min_row, min_col, max_row, max_col)


@dataclass
class FlakingResult:
    candidates: list[FlakingCandidate]
    reference_width_px: float  # [measured] this image's median skeleton-sampled crack width
    excluded_mask: np.ndarray  # bool, same shape as the input mask
    mask_corrected: np.ndarray  # bool -- mask_clean with excluded_mask subtracted
    excluded_area_px2: int  # [measured]
    excluded_area_pct: float  # [measured] of the full image


def compute_reference_width_px(skel_image: np.ndarray, medial_radius: np.ndarray) -> float:
    """Median local width (2 * medial_radius) sampled at every skeleton
    pixel. Median, not mean, so a candidate blob's own messy interior
    skeleton (a small fraction of total skeleton mileage against a whole
    image of normal crack) can't drag this reference value up -- see module
    docstring."""
    if not skel_image.any():
        return 0.0
    return float(np.median(2.0 * medial_radius[skel_image]))


def identify_candidates(
    mask_clean: np.ndarray,
    medial_radius: np.ndarray,
    reference_width_px: float,
    *,
    K: float = WIDTH_FLAG_MULTIPLIER_K,
    min_area_px2: int = MIN_CANDIDATE_AREA_PX2,
) -> tuple[list[FlakingCandidate], np.ndarray]:
    """Returns (candidates, labeled_wide_mask) -- the label image is needed
    by grow_and_exclude to recover each candidate's own flagged seed
    pixels. Width (+ minimum area) is the single identification criterion
    -- see module docstring for why a second, solidity-based criterion was
    tried and dropped."""
    if reference_width_px <= 0:
        return [], np.zeros(mask_clean.shape, dtype=int)

    width_threshold_px = K * reference_width_px
    wide_mask = (2.0 * medial_radius > width_threshold_px) & mask_clean
    labeled = label(wide_mask)

    candidates = [
        FlakingCandidate(label=rp.label, area_px2=int(rp.area), solidity=float(rp.solidity), bbox=rp.bbox)
        for rp in regionprops(labeled)
        if rp.area >= min_area_px2
    ]
    return candidates, labeled


def _grow_one_candidate(
    seed: np.ndarray, local_mask: np.ndarray, *, growth_cap_px: float, step_px: int
) -> np.ndarray:
    struct = disk(step_px)
    n_steps = int(np.ceil(growth_cap_px / step_px))
    grown = seed.copy()
    for _ in range(n_steps):
        new_grown = binary_dilation(grown, footprint=struct) & local_mask
        if int(new_grown.sum()) == int(grown.sum()):
            return new_grown
        grown = new_grown
    return grown


def grow_and_exclude(
    candidates: list[FlakingCandidate],
    labeled_wide_mask: np.ndarray,
    mask_clean: np.ndarray,
    reference_width_px: float,
    *,
    growth_multiplier: float = GROWTH_MULTIPLIER,
    step_px: int = GROWTH_STEP_PX,
) -> np.ndarray:
    """Grow each candidate's seed outward, constrained to stay inside
    mask_clean, up to growth_multiplier * reference_width_px. Returns the
    union of all grown regions as a full-image boolean mask. Cropped to
    each candidate's own padded bounding box for efficiency -- safe, not
    lossy, because growth is inherently local (see module docstring)."""
    h, w = mask_clean.shape
    excluded_mask = np.zeros((h, w), dtype=bool)
    growth_cap_px = growth_multiplier * reference_width_px
    pad = int(growth_cap_px) + 50

    for c in candidates:
        y0, x0, y1, x1 = c.bbox
        cy0, cy1 = max(0, y0 - pad), min(h, y1 + pad)
        cx0, cx1 = max(0, x0 - pad), min(w, x1 + pad)
        local_mask = mask_clean[cy0:cy1, cx0:cx1]
        seed = labeled_wide_mask[cy0:cy1, cx0:cx1] == c.label
        grown = _grow_one_candidate(seed, local_mask, growth_cap_px=growth_cap_px, step_px=step_px)
        excluded_mask[cy0:cy1, cx0:cx1] |= grown

    return excluded_mask


def exclude_flaking_regions(
    mask_clean: np.ndarray,
    skel_image: np.ndarray,
    medial_radius: np.ndarray,
    *,
    K: float = WIDTH_FLAG_MULTIPLIER_K,
    min_area_px2: int = MIN_CANDIDATE_AREA_PX2,
    growth_multiplier: float = GROWTH_MULTIPLIER,
    step_px: int = GROWTH_STEP_PX,
) -> FlakingResult:
    """Top-level orchestrator: identify candidates from a scout
    skeletonization pass (mask_clean/skel_image/medial_radius, i.e.
    skeletonize_and_prune's own output -- no separate extract_graph() call
    needed for this), grow them to recover their true boundary, and return
    the corrected mask ready for a second, real skeletonize_and_prune call.
    If no candidates are found, mask_corrected == mask_clean and the caller
    can skip the second pass entirely."""
    reference_width_px = compute_reference_width_px(skel_image, medial_radius)
    candidates, labeled_wide_mask = identify_candidates(
        mask_clean, medial_radius, reference_width_px,
        K=K, min_area_px2=min_area_px2,
    )

    if not candidates:
        excluded_mask = np.zeros(mask_clean.shape, dtype=bool)
    else:
        excluded_mask = grow_and_exclude(
            candidates, labeled_wide_mask, mask_clean, reference_width_px,
            growth_multiplier=growth_multiplier, step_px=step_px,
        )

    mask_corrected = mask_clean & ~excluded_mask
    excluded_area_px2 = int(excluded_mask.sum())
    excluded_area_pct = 100.0 * excluded_area_px2 / mask_clean.size

    return FlakingResult(
        candidates=candidates,
        reference_width_px=reference_width_px,
        excluded_mask=excluded_mask,
        mask_corrected=mask_corrected,
        excluded_area_px2=excluded_area_px2,
        excluded_area_pct=excluded_area_pct,
    )


def cut_adjacent_path_indices(
    skeleton,
    graph_result,
    excluded_mask: np.ndarray,
    reference_width_px: float,
    *,
    buffer_width_multiplier: float = CUT_ADJACENT_BUFFER_WIDTH_MULTIPLIER,
) -> set[int]:
    """Path indices of edges whose skeleton path comes within
    buffer_width_multiplier * reference_width_px of excluded_mask at ANY
    point along the path -- not just at an endpoint node. A truncated
    stub's endpoint will always be close, but a
    disk-dilation growth frontier is rounded, not a straight guillotine
    cut, so it can graze alongside a corridor's wall for a stretch without
    fully severing it -- in that case the edge survives as one piece with
    both real endpoints far away, but its *path* still runs right next to
    an artificial, algorithm-introduced boundary partway along. Checking
    only the endpoints would miss exactly that case.

    Flagged edges' length/width are not real measurements and should be
    dropped from those statistics.

    Deliberately geometric (distance to a mask we already computed), not
    based on junction type/angle classification -- topology right at a cut
    can be genuinely irregular, so classifying it first and trusting that
    classification would be asking the least reliable part of the pipeline
    to police itself. See flaking.py module docstring and CLAUDE.md's
    "emit no constraint rather than a low-confidence guess" principle.

    The buffer mask is built via distance_transform_edt thresholded at
    buffer_px, not skimage's binary_dilation(disk(...)) -- "within radius R
    of excluded_mask" is exactly what a disk-footprint dilation computes
    too, but large-footprint morphological dilation over a full-resolution
    (~7250x7600px) image is dramatically slower than EDT for the same
    result: measured on T2-A_membran_v2, 242.8s (dilation) vs 6.6s (EDT),
    with the output mask and flagged-edge set coming out 100% pixel- and
    set-identical -- not an approximation, the same computation done
    faster. This was the single largest cost in the whole crack-stats
    pipeline before this change (~80% of one image's total runtime).
    """
    if not excluded_mask.any() or len(graph_result.summary) == 0:
        return set()

    buffer_px = buffer_width_multiplier * reference_width_px
    buffer_px_int = max(1, int(np.ceil(buffer_px)))
    buffer_mask = distance_transform_edt(~excluded_mask) <= buffer_px_int
    h, w = excluded_mask.shape

    flagged = set()
    for path_index in graph_result.summary.index:
        coords = skeleton.path_coordinates(int(path_index))
        rr = np.clip(np.round(coords[:, 0]).astype(int), 0, h - 1)
        cc = np.clip(np.round(coords[:, 1]).astype(int), 0, w - 1)
        if buffer_mask[rr, cc].any():
            flagged.add(int(path_index))

    return flagged
