"""Find flaked-off catalyst-layer patches and exclude them from the crack mask.

A flaked patch is bright under Otsu like a crack, but it is missing material,
not a fracture, and hides whatever crack pattern was underneath.

- Identify: pixels wider than WIDTH_FLAG_MULTIPLIER_K x this image's median
  crack width, in regions of at least MIN_CANDIDATE_AREA_PX2. Width is the only
  criterion; a solidity criterion was tried and dropped.
- Exclude: grow each region back out to its true edge (GROWTH_MULTIPLIER),
  staying inside the mask.
- Edges: the mask is skeletonized once; any skeleton edge with a pixel inside
  the excluded region is omitted from the stats and the connectivity graph
  (flake_touching_path_indices).

Constants are 🔴 assumed unless noted. Full rationale:
docs/design_notes.md, section "flaking.py".
"""

from dataclasses import dataclass, field

import numpy as np
from skimage.measure import label, regionprops
from skimage.morphology import binary_dilation, disk

from .graph import GraphResult, extract_graph, path_pixel_indices

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
    """Top-level orchestrator: identify candidates from skeletonize_and_prune's
    own output (mask_clean/skel_image/medial_radius -- no extract_graph() call
    needed), grow them to recover their true boundary, and return the excluded
    region. mask_corrected (mask_clean minus the excluded region) is the crack
    area outside flakes; the skeleton itself is not rebuilt -- callers drop
    flake-touching edges with flake_touching_path_indices. If no candidates are
    found, mask_corrected == mask_clean."""
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


def flake_touching_path_indices(
    skeleton,
    graph_result,
    excluded_mask: np.ndarray,
) -> set[int]:
    """Path indices of edges with at least one pixel inside excluded_mask.

    Callers omit these edges from both the stats and the connectivity graph.
    No distance buffer is needed: the skeleton is built once from the
    uncorrected mask, so the excluded region itself (not a margin around it)
    is exactly where the skeleton is flaking noise rather than real crack.
    Coordinates are clipped/rounded (path_pixel_indices) so a path touching
    the image border can't index out of bounds.
    """
    if not excluded_mask.any() or len(graph_result.summary) == 0:
        return set()

    flagged = set()
    for path_index in graph_result.summary.index:
        rr, cc = path_pixel_indices(skeleton.path_coordinates(int(path_index)), excluded_mask.shape)
        if excluded_mask[rr, cc].any():
            flagged.add(int(path_index))

    return flagged


def remove_flake_touching_edges(skeleton, graph_result: GraphResult, excluded_mask: np.ndarray):
    """Remove flake-touching edges from the skeleton itself and rebuild the graph.

    For tools that analyse the graph (junctions, curvature, anisotropy) rather
    than only summing stats over it: "omitted from the connectivity graph" then
    has to mean the edges are gone. Their neighbours merge where a junction
    loses a branch. Returns (skeleton, graph_result, omitted path indices of the
    input graph). Unchanged if nothing touches a flake.
    """
    omitted = flake_touching_path_indices(skeleton, graph_result, excluded_mask)
    if not omitted:
        return skeleton, graph_result, omitted
    pruned = skeleton.prune_paths(np.array(sorted(omitted)))
    return pruned, extract_graph(pruned), omitted
