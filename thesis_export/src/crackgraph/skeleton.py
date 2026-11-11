"""Stage 2: thin the crack mask to a 1-px skeleton, then prune junk branches.

Thinning is skimage's Zhang algorithm. Pruning repeats until nothing changes
(removing one branch can expose another) and removes dead-end or isolated
branches that are either:
- shorter than SPUR_PX_PLACEHOLDER (spurs, fragments), or
- host stubs: dead ends with less than SPUR_PX_PLACEHOLDER of their length outside
  the crack they branch from (centre-to-wall stubs into bumps and corners).

Known, unfixed limitation: loops around dark specks above the fill limit, and short edges
between close junctions, are never removed by this pruning (see design_notes.md).

Full rationale (measurements, rejected alternatives, references):
docs/design_notes.md, section "skeleton.py".
"""

from dataclasses import dataclass

import numpy as np
import skan
from scipy.ndimage import distance_transform_edt
from scipy.spatial import cKDTree
from skimage.morphology import remove_small_holes, remove_small_objects, skeletonize

# Tunable settings. Full rationale for each: docs/calibration_notes.md.

# SPUR_PX_PLACEHOLDER: dead ends/isolated branches shorter than this (px) are pruned. 15 px = 9.1 um
# (mm images only) ~ largest agglomerates and film thickness. 🟢, see docs/calibration_notes.md.
SPUR_PX_PLACEHOLDER = 15

# DARK_SPECK_AREA_PX2: dark specks (holes) inside a crack smaller than this
# (px^2) are filled before thinning, so the skeleton doesn't loop around them.
# 130 px^2 = 48 um^2, the area of a d90 ~ 7.8 um agglomerate (inks T2-T4).
# 🟢, see docs/calibration_notes.md. mm images only.
DARK_SPECK_AREA_PX2 = 130


@dataclass
class PrunedBranchRecord:
    """One pruned branch's full pixel path, kept for later diagnostic
    visualization (e.g. "what got cut and why") without having to re-run
    the analysis -- SkeletonResult's length-only fields exist for the
    console report and aren't enough to redraw a branch's location."""

    reason: str  # "spur" | "fragment" | "host_stub"
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
    n_host_stubs_pruned: int  # [measured]
    pruned_host_stub_lengths: list[float]  # [measured], px (full branch length, not the outside part)
    prune_host_stubs: bool  # whether the host-stub rule was on
    pruned_branches: list[PrunedBranchRecord]  # [measured] every pruned branch, coords + reason
    iters_used: int


def _length_outside_host(
    skel: skan.Skeleton,
    incidence: dict[int, list[int]],
    path_index: int,
    node_id_src: int,
    node_id_dst: int,
    medial_radius: np.ndarray,
) -> float | None:
    """Arc length (px) of a dead end's path lying outside the crack it branches from.

    The host is the other branches at the dead end's junction. Its half-width
    r_host is the median medial radius along them, 1-3 junction-blob radii out
    (so the wider blob where cracks meet doesn't inflate it). A dead-end pixel
    counts as outside if it is farther than r_host from the host centre line.
    None if the junction has no other branch to measure.
    """
    j = node_id_dst if skel.degrees[node_id_dst] >= 3 else node_id_src
    jc = np.asarray(skel.coordinates[j], dtype=float)
    r_blob = float(medial_radius[tuple(np.round(jc).astype(int))])
    widths, host_pts = [], []
    for k in incidence.get(j, []):
        if k == path_index:
            continue
        co = skel.path_coordinates(k)
        host_pts.append(co)
        d = np.hypot(*(co - jc).T)
        near = (d >= r_blob) & (d <= 3 * max(r_blob, 1.0))
        c = np.round(co[near] if near.any() else co).astype(int)
        widths.extend(medial_radius[c[:, 0], c[:, 1]].tolist())
    if not host_pts:
        return None
    r_host = float(np.median(widths))
    coords = skel.path_coordinates(path_index)
    d_host = cKDTree(np.vstack(host_pts)).query(coords)[0]
    steps = np.hypot(*np.diff(coords, axis=0).T)
    return float(steps[d_host[1:] > r_host].sum())


def skeletonize_and_prune(
    mask: np.ndarray,
    *,
    source_image: np.ndarray | None = None,
    min_object_px: int = 4,
    spur_px: float = SPUR_PX_PLACEHOLDER,
    prune_host_stubs: bool = True,
    max_iters: int = 10,
) -> SkeletonResult:
    mask_clean = remove_small_objects(mask, min_size=min_object_px)
    mask_clean = remove_small_holes(mask_clean, area_threshold=DARK_SPECK_AREA_PX2)
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
    pruned_host_stub_lengths: list[float] = []
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

        # Host-stub check: dead ends the length rule didn't catch, but with less
        # than spur_px of their length outside the crack they branch from.
        host_stub_rows = summary.index[:0]
        if prune_host_stubs:
            incidence: dict[int, list[int]] = {}
            for k, a_, b_ in zip(summary.index, summary["node_id_src"], summary["node_id_dst"]):
                incidence.setdefault(int(a_), []).append(k)
                incidence.setdefault(int(b_), []).append(k)
            eligible = summary.index[(summary["branch_type"] == 1) & ~summary.index.isin(length_flagged_rows)]
            flags = []
            for k in eligible:
                outside = _length_outside_host(
                    skel, incidence, int(k),
                    int(summary.at[k, "node_id_src"]), int(summary.at[k, "node_id_dst"]), medial_radius,
                )
                flags.append(outside is not None and outside < spur_px)
            host_stub_rows = eligible[np.array(flags, dtype=bool)]

        if len(spur_rows) == 0 and len(fragment_rows) == 0 and len(host_stub_rows) == 0:
            break
        pruned_spur_lengths.extend(summary.loc[spur_rows, "branch_distance"].tolist())
        pruned_fragment_lengths.extend(summary.loc[fragment_rows, "branch_distance"].tolist())
        pruned_host_stub_lengths.extend(summary.loc[host_stub_rows, "branch_distance"].tolist())

        # Coordinates must be captured now, before prune_paths() below --
        # skel is replaced with a fresh Skeleton each call and path indices
        # are not stable across that boundary.
        for reason, rows in (
            ("spur", spur_rows),
            ("fragment", fragment_rows),
            ("host_stub", host_stub_rows),
        ):
            for path_index in rows:
                pruned_branches.append(
                    PrunedBranchRecord(
                        reason=reason,
                        branch_distance=float(summary.at[path_index, "branch_distance"]),
                        coords=skel.path_coordinates(int(path_index)),
                    )
                )

        all_rows = length_flagged_rows.union(host_stub_rows)
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
        n_host_stubs_pruned=len(pruned_host_stub_lengths),
        pruned_host_stub_lengths=pruned_host_stub_lengths,
        prune_host_stubs=prune_host_stubs,
        pruned_branches=pruned_branches,
        iters_used=iters_used,
    )
