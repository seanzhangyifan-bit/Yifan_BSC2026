"""Stage 2: skeletonize + prune short spurs.

Homotopy-preserving thinning (skimage's Zhang's algorithm), followed by
iterative spur pruning via skan.Skeleton.prune_paths. Pruning is iterative,
not a single pass: removing a spur can expose a new short branch at a
junction that was previously higher-valence, so a single pass under-prunes.
"""

from dataclasses import dataclass

import numpy as np
import skan
from skimage.morphology import remove_small_objects, skeletonize

# [PLACEHOLDER] Not derived from real film-thickness h or a calibrated
# um-per-pixel value -- neither exists yet (calibration is supplied
# manually, later). Chosen only as "somewhat larger than the annulus
# inner-radius jitter scale (a few px)" that CLAUDE.md mentions elsewhere,
# so as to not eat real short branches. Must be revisited once calibration
# lands.
SPUR_PX_PLACEHOLDER = 15


@dataclass
class SkeletonResult:
    skeleton: skan.Skeleton
    skel_image: np.ndarray
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
        n_pixels_pre_prune=n_pixels_pre,
        n_pixels_post_prune=n_pixels_post,
        n_spurs_pruned=len(pruned_spur_lengths),
        pruned_spur_lengths=pruned_spur_lengths,
        n_fragments_pruned=len(pruned_fragment_lengths),
        pruned_fragment_lengths=pruned_fragment_lengths,
        spur_px_threshold=spur_px,
        iters_used=iters_used,
    )
