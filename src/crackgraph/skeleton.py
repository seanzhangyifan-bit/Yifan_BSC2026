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
"""

from dataclasses import dataclass

import numpy as np
import skan
from scipy.ndimage import distance_transform_edt
from skimage.morphology import remove_small_objects, skeletonize

SPUR_PX_PLACEHOLDER = 15  # 🔴 assumed — see CALIBRATION.md


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
    iters_used: int


def skeletonize_and_prune(
    mask: np.ndarray,
    *,
    source_image: np.ndarray | None = None,
    min_object_px: int = 4,
    spur_px: float = SPUR_PX_PLACEHOLDER,
    max_iters: int = 10,
) -> SkeletonResult:
    mask_clean = remove_small_objects(mask, min_size=min_object_px)
    skel_image = skeletonize(mask_clean)
    n_pixels_pre = int(skel_image.sum())

    # Local crack half-width at every mask pixel -- used downstream (stage
    # 4, junctions.py) to keep the annulus fit band outside the junction
    # blob (which can be wider than a fixed inner-radius placeholder), and
    # groundwork for CLAUDE.md's width chronometer (post-crack drying
    # shrinkage: earlier cracks tend wider).
    medial_radius = distance_transform_edt(mask_clean)

    skel = skan.Skeleton(skel_image, source_image=source_image)

    pruned_spur_lengths: list[float] = []
    pruned_fragment_lengths: list[float] = []
    iters_used = 0

    for i in range(max_iters):
        summary = skan.summarize(skel, separator="_")
        if len(summary) == 0:
            break
        is_spur = (summary["branch_type"] == 1) & (summary["branch_distance"] < spur_px)
        is_fragment = (summary["branch_type"] == 0) & (summary["branch_distance"] < spur_px)
        spur_rows = summary.index[is_spur]
        fragment_rows = summary.index[is_fragment]
        if len(spur_rows) == 0 and len(fragment_rows) == 0:
            break
        pruned_spur_lengths.extend(summary.loc[spur_rows, "branch_distance"].tolist())
        pruned_fragment_lengths.extend(summary.loc[fragment_rows, "branch_distance"].tolist())
        all_rows = spur_rows.union(fragment_rows)
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
        iters_used=iters_used,
    )
