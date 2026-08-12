"""Stage 2: skeletonize + prune short spurs.

Homotopy-preserving thinning (skimage's Zhang's algorithm), followed by
iterative spur pruning via skan.Skeleton.prune_paths. Pruning is iterative,
not a single pass: removing a spur can expose a new short branch at a
junction that was previously higher-valence, so a single pass under-prunes.

KNOWN LIMITATION -- spurious skeleton loops, not fixed by spur_px: Zhang's
thinning is pixel-local (each pixel is erased or kept based only on its
immediate neighborhood, never on the shape's overall width or center), so
on a locally wide or slightly irregular crack band it can trace both edges
of the band for a short stretch before merging back into one line, leaving
a small closed loop instead of a single centerline. This is a well-known
general sensitivity of skeleton/medial-axis methods to boundary noise, not
specific to this codebase.

The pruning loop above is structurally blind to this: it only ever removes
branch_type 0 (isolated fragment) and branch_type 1 (spur, one endpoint
degree-1) branches, never branch_type 2 (junction-to-junction) or 3
(cycle) -- and a loop's two strands are anchored to the graph at both
ends, so they are always type 2 or 3, regardless of how spur_px is tuned.

Measured, not assumed: `scripts/skeleton_loop_sweep.py` audits every image
in the real dataset for junction-to-junction edges shorter than that
image's own average crack width (the fingerprint of this artifact). Result
across the 39-image dataset: 0% to 55.2% of all edges per image, only
weakly correlated with average crack width (r ~ 0.31 against
avg_width_px) and NOT cleanly explained by substrate -- Membran and PTFE
samples have essentially the same mean (~9.7% vs ~9.3%), and the single
worst offender in the dataset is a Membran sample. This inflates n_edges
and deflates avg_edge_length_px for affected images (see
docs/crack_stats_schema.md S4); it has a much larger effect on the planned
junction-census/T-vs-Y work, since many of the extra "junctions" this
creates aren't real crack meetings. No fix is implemented yet -- documented
as a known, measured limitation, not silently worked around.

Corner-tracing artifacts (in addition to plain short spurs): the medial
axis transform mathematically *must* trace a skeleton branch into every
concave corner of the mask boundary -- this is not thinning noise, it is a
correct property of the medial axis, and it is blind to length. A branch
tracing into a real notch (e.g. the ragged edge of a flaked-off region, or
a background inlet between two crack walls) can be far longer than
SPUR_PX_PLACEHOLDER and survive flat-length pruning untouched. Confirmed on
a real case this session (T2-A_membran_v2): a branch with a near-perfectly
linear 2.0px -> 121.7px width ramp over 45px, visually confirmed tracing
into a real black wedge with no crack present.

Two other criteria were tried and rejected before settling on the one
below: a windowed tip-width comparison (too conservative, missed
medium/long artifacts entirely) and a "fraction of the branch above its own
tip-median width" test (mathematically flawed -- for a genuinely real,
noisy-but-stable-width crack, the tip-region median is a random draw from
the same distribution as the rest of the branch, so ~50% of pixels exceed
it by symmetric noise alone; the >50% threshold sat right at a coin flip
for exactly the branches that should survive).

What is used instead: the Pearson correlation between pixel position
(0 = the free tip, where one exists) and local width (2 * medial_radius)
along the branch. A genuine crack's width is noisy but flat around a
steady value -> correlation near 0. A corner-tracing artifact's width
ramps monotonically toward the notch it's chasing -> correlation near +1.
This sidesteps the coin-flip problem because it tests for a trend, not a
fraction above a reference drawn from the same noisy population.

This targets the same general problem as several standard skeleton-pruning
methods from the literature -- Discrete Curve Evolution pruning (Bai, Liu &
Latecki, IEEE TPAMI 2007), the lambda-medial-axis (Chazal & Lieutier,
Graphical Models 2005), and the scale-axis transform (Giesen et al., SoCG
2009) -- but the correlation test here is a much simpler, single-parameter
stand-in, not a reimplementation of any of them.
"""

from dataclasses import dataclass

import numpy as np
import skan
from scipy.ndimage import distance_transform_edt
from skimage.morphology import remove_small_holes, remove_small_objects, skeletonize

SPUR_PX_PLACEHOLDER = 15  # 🔴 assumed — see CALIBRATION.md

# Area (px^2) below which a fully-enclosed background hole inside the
# foreground mask gets filled in, right after remove_small_objects and
# before skeletonize(). A tiny thresholding gap inside an otherwise-solid
# crack (dust, a faint pixel, a one-off segmentation miss) is still one
# crack, not two -- left unfilled it can force the skeleton to trace
# around it, producing a spurious small loop/branch at that exact spot.
# 50 px^2 is carried over unchanged from an earlier prototype comparison
# script (informal, not swept or independently derived here) -- see
# CALIBRATION.md.
HOLE_AREA_THRESHOLD_PX2 = 50

# Pearson correlation (pixel position vs. local width) above which a
# branch is treated as a corner-tracing medial-axis artifact rather than a
# real crack spur. Swept at 0.8/0.9/0.95/0.99 on T2-A_membran_v2's full
# image (1439 eligible branches; 229/187/139/84 flagged respectively) and
# reviewed visually at matched crops: raising the threshold sheds short
# corner-artifact chains (one chain of 6 short zigzag spurs went from 6/6
# flagged at 0.8 to 1/6 at 0.99) while nothing inspected suggested 0.8 was
# flagging genuine open-field cracks. 0.99 was chosen to prioritize never
# touching a real crack over catching every short artifact. 🟡 empirical,
# uncalibrated — see CALIBRATION.md.
CORR_THRESHOLD = 0.99

# Minimum branch length (px) for the correlation test to be meaningful at
# all; shorter branches don't have enough points for a Pearson correlation
# to mean anything, so they're never flagged by this criterion -- emit no
# constraint rather than guess, per METHODOLOGY.md's near-120-degree-junction
# precedent. 🔴 assumed — see CALIBRATION.md.
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
    rr = np.clip(np.round(coords[:, 0]).astype(int), 0, medial_radius.shape[0] - 1)
    cc = np.clip(np.round(coords[:, 1]).astype(int), 0, medial_radius.shape[1] - 1)
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
