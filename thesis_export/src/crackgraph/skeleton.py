"""Stage 2: thin the crack mask to a 1-px skeleton, then prune junk branches.

Thinning is skimage's Zhang algorithm. Pruning repeats until nothing changes
(removing one branch can expose another) and removes dead-end or isolated
branches that are either:
- shorter than SPUR_PX_PLACEHOLDER (spurs, fragments), or
- corner-tracing artifacts: width ramps steadily toward a concave corner of the
  mask (position-vs-width correlation above CORR_THRESHOLD).

Known, measured, unfixed limitation: on wide or ragged cracks, thinning can
leave small junction-to-junction loops, which this pruning never removes.

Full rationale (measurements, rejected alternatives, references):
docs/design_notes.md, section "skeleton.py".
"""

from dataclasses import dataclass

import numpy as np
import skan
from scipy.ndimage import distance_transform_edt
from skimage.morphology import remove_small_holes, remove_small_objects, skeletonize

from .graph import path_pixel_indices

# Tunable settings. Full rationale for each: docs/calibration_notes.md.

# SPUR_PX_PLACEHOLDER: dead ends/isolated branches shorter than this (px) are pruned. 15 px = 9.1 um
# (mm images only) ~ largest agglomerates and film thickness. 🟢, see docs/calibration_notes.md.
SPUR_PX_PLACEHOLDER = 15

# HOLE_AREA_THRESHOLD_PX2: holes inside a crack smaller than this (px^2) are
# filled before thinning, so the skeleton doesn't loop around them.
# 🔴 assumed, carried over from an earlier prototype.
HOLE_AREA_THRESHOLD_PX2 = 50

# CORR_THRESHOLD: a branch whose width rises with position along it more
# steadily than this (Pearson correlation) is pruned as a corner-tracing
# artifact. Set high so real cracks are never removed.
# 🟡 empirical: hand-swept 0.8-0.99 on one image.
CORR_THRESHOLD = 0.99

# MIN_LEN_FOR_CORR_PX: branches shorter than this (px) skip the correlation
# test, since too few points make the correlation meaningless. 🔴 assumed.
MIN_LEN_FOR_CORR_PX = 4


@dataclass
class PrunedBranchRecord:
    """One pruned branch's full pixel path, kept for later diagnostic
    visualization (e.g. "what got cut and why") without having to re-run
    the analysis -- SkeletonResult's length-only fields exist for the
    console report and aren't enough to redraw a branch's location."""

    reason: str  # "spur" | "fragment" | "corner_artifact"
    branch_distance: float  # [measured], px
    coords: np.ndarray  # (N, 2) row, col -- captured via skel.path_coordinates() before pruning


@dataclass
class SkeletonResult:
    skeleton: skan.Skeleton
    skel_image: np.ndarray
    mask_clean: np.ndarray  # [measured] despeckled foreground mask (post remove_small_objects), pre-skeletonize
    medial_radius: np.ndarray  # [measured] EDT of the cleaned mask: local crack half-width (px) at every pixel
    n_pixels_pre_prune: int  # [measured]
    n_pixels_post_prune: int  # [measured]
    n_spurs_pruned: int  # [measured]
    pruned_spur_lengths: list[float]  # [measured], px
    n_fragments_pruned: int  # [measured]
    pruned_fragment_lengths: list[float]  # [measured], px
    spur_px_threshold: float  # [PLACEHOLDER]
    n_corner_artifacts_pruned: int  # [measured]
    pruned_corner_artifact_lengths: list[float]  # [measured], px
    corner_artifact_corr_threshold: float | None  # [PLACEHOLDER], None = criterion disabled
    pruned_branches: list[PrunedBranchRecord]  # [measured] every pruned branch, coords + reason
    iters_used: int


def _tip_ordered_width_profile(
    skel: skan.Skeleton,
    medial_radius: np.ndarray,
    path_index: int,
    node_id_src: int,
    node_id_dst: int,
) -> np.ndarray:
    """Local width (2 * medial_radius) along a branch's pixel path, ordered
    so index 0 is the free (degree-1) end when the branch has one. Both
    ends of a branch_type==0 isolated fragment are degree-1; in that case
    the orientation is arbitrary (there is no junction to trace away
    from)."""
    coords = skel.path_coordinates(int(path_index))
    if skel.degrees[int(node_id_dst)] == 1:
        coords = coords[::-1]
    rr, cc = path_pixel_indices(coords, medial_radius.shape)
    return 2.0 * medial_radius[rr, cc]


def is_corner_tracing_artifact(
    widths: np.ndarray,
    *,
    corr_threshold: float = CORR_THRESHOLD,
    min_len_px: int = MIN_LEN_FOR_CORR_PX,
) -> bool:
    """True if width trends monotonically with position along the branch
    (a corner-tracing medial-axis artifact) rather than staying flat
    (a genuine, noisy-but-stable-width crack). See module docstring for
    why correlation, not a fixed-reference fraction, is used."""
    n = len(widths)
    if n < min_len_px:
        return False
    if widths.std() == 0:
        return False
    positions = np.arange(n)
    corr = np.corrcoef(positions, widths)[0, 1]
    return bool(corr > corr_threshold)


def skeletonize_and_prune(
    mask: np.ndarray,
    *,
    source_image: np.ndarray | None = None,
    min_object_px: int = 4,
    spur_px: float = SPUR_PX_PLACEHOLDER,
    corner_artifact_corr_threshold: float | None = CORR_THRESHOLD,
    max_iters: int = 10,
) -> SkeletonResult:
    mask_clean = remove_small_objects(mask, min_size=min_object_px)
    mask_clean = remove_small_holes(mask_clean, area_threshold=HOLE_AREA_THRESHOLD_PX2)
    skel_image = skeletonize(mask_clean)
    n_pixels_pre = int(skel_image.sum())

    # Local crack half-width at every mask pixel -- used downstream (stage
    # 4, junctions.py) to keep the annulus fit band outside the junction
    # blob (which can be wider than a fixed inner-radius placeholder), and
    # groundwork for METHODOLOGY.md's width chronometer (post-crack drying
    # shrinkage: earlier cracks tend wider).
    medial_radius = distance_transform_edt(mask_clean)

    skel = skan.Skeleton(skel_image, source_image=source_image)

    pruned_spur_lengths: list[float] = []
    pruned_fragment_lengths: list[float] = []
    pruned_corner_artifact_lengths: list[float] = []
    pruned_branches: list[PrunedBranchRecord] = []
    iters_used = 0

    for i in range(max_iters):
        summary = skan.summarize(skel, separator="_")
        if len(summary) == 0:
            break
        is_spur = (summary["branch_type"] == 1) & (summary["branch_distance"] < spur_px)
        is_fragment = (summary["branch_type"] == 0) & (summary["branch_distance"] < spur_px)
        spur_rows = summary.index[is_spur]
        fragment_rows = summary.index[is_fragment]
        length_flagged_rows = spur_rows.union(fragment_rows)

        # Corner-artifact check: only for branches the length-based
        # criterion didn't already catch -- it exists specifically for the
        # medium/long artifacts spur_px is blind to (see module docstring),
        # so keep the two pruning reasons mutually exclusive for reporting.
        corner_artifact_rows = summary.index[:0]
        if corner_artifact_corr_threshold is not None:
            corner_eligible = summary.index[
                summary["branch_type"].isin((0, 1)) & ~summary.index.isin(length_flagged_rows)
            ]
            is_corner_artifact = [
                is_corner_tracing_artifact(
                    _tip_ordered_width_profile(
                        skel, medial_radius, path_index,
                        summary.at[path_index, "node_id_src"], summary.at[path_index, "node_id_dst"],
                    ),
                    corr_threshold=corner_artifact_corr_threshold,
                )
                for path_index in corner_eligible
            ]
            corner_artifact_rows = corner_eligible[np.array(is_corner_artifact, dtype=bool)]

        if len(spur_rows) == 0 and len(fragment_rows) == 0 and len(corner_artifact_rows) == 0:
            break
        pruned_spur_lengths.extend(summary.loc[spur_rows, "branch_distance"].tolist())
        pruned_fragment_lengths.extend(summary.loc[fragment_rows, "branch_distance"].tolist())
        pruned_corner_artifact_lengths.extend(summary.loc[corner_artifact_rows, "branch_distance"].tolist())

        # Coordinates must be captured now, before prune_paths() below --
        # skel is replaced with a fresh Skeleton each call and path indices
        # are not stable across that boundary.
        for reason, rows in (
            ("spur", spur_rows),
            ("fragment", fragment_rows),
            ("corner_artifact", corner_artifact_rows),
        ):
            for path_index in rows:
                pruned_branches.append(
                    PrunedBranchRecord(
                        reason=reason,
                        branch_distance=float(summary.at[path_index, "branch_distance"]),
                        coords=skel.path_coordinates(int(path_index)),
                    )
                )

        all_rows = length_flagged_rows.union(corner_artifact_rows)
        skel = skel.prune_paths(all_rows.to_numpy())
        iters_used = i + 1

    n_pixels_post = int(skel.skeleton_image.sum())

    return SkeletonResult(
        skeleton=skel,
        skel_image=skel.skeleton_image,
        mask_clean=mask_clean,
        medial_radius=medial_radius,
        n_pixels_pre_prune=n_pixels_pre,
        n_pixels_post_prune=n_pixels_post,
        n_spurs_pruned=len(pruned_spur_lengths),
        pruned_spur_lengths=pruned_spur_lengths,
        n_fragments_pruned=len(pruned_fragment_lengths),
        pruned_fragment_lengths=pruned_fragment_lengths,
        spur_px_threshold=spur_px,
        n_corner_artifacts_pruned=len(pruned_corner_artifact_lengths),
        pruned_corner_artifact_lengths=pruned_corner_artifact_lengths,
        corner_artifact_corr_threshold=corner_artifact_corr_threshold,
        pruned_branches=pruned_branches,
        iters_used=iters_used,
    )
