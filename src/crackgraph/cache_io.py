"""Per-image analysis cache: save/load the arrays and records a later
session needs to regenerate a stats row, an overlay, or a "what got cut and
why" diagnostic view without re-running binarize/skeletonize/prune on the
full-resolution image.

Deliberately not caching medial_radius -- a full-resolution float array,
large, and cheap to regenerate on demand from mask_corrected
(scipy.ndimage.distance_transform_edt, a single vectorized call), unlike
everything else here which is either expensive to reproduce (skeletonize +
iterative pruning) or a small, fully-specified record (pruned_branches,
stats).

pruned_branches.npz mirrors skan's own indptr/coords convention (this
codebase already depends on that mental model via skan.Skeleton) rather
than inventing a new ragged-array format: coords_flat is every pruned
branch's (row, col) polyline concatenated end to end, coords_indptr marks
where each branch's own slice starts/ends within it.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import json

from .flaking import FlakingCandidate, FlakingResult
from .skeleton import PrunedBranchRecord, SkeletonResult


@dataclass
class AnalysisCache:
    stats_row: dict
    mask_corrected: np.ndarray  # bool
    skeleton_final: np.ndarray  # bool
    excluded_mask: np.ndarray  # bool
    flaking_candidates: list[FlakingCandidate]
    reference_width_px: float  # [measured]
    excluded_area_px2: int  # [measured]
    excluded_area_pct: float  # [measured]
    pruned_branches: list[PrunedBranchRecord]


def _pruned_branches_to_npz_arrays(pruned_branches: list[PrunedBranchRecord]) -> dict[str, np.ndarray]:
    reasons = np.array([b.reason for b in pruned_branches], dtype=object)
    distances = np.array([b.branch_distance for b in pruned_branches], dtype=np.float64)
    coords_indptr = np.zeros(len(pruned_branches) + 1, dtype=np.int64)
    for i, b in enumerate(pruned_branches):
        coords_indptr[i + 1] = coords_indptr[i] + len(b.coords)
    if pruned_branches:
        coords_flat = np.concatenate([b.coords for b in pruned_branches], axis=0).astype(np.float64)
    else:
        coords_flat = np.zeros((0, 2), dtype=np.float64)
    return {
        "reasons": reasons,
        "distances": distances,
        "coords_flat": coords_flat,
        "coords_indptr": coords_indptr,
    }


def _pruned_branches_from_npz(npz: np.lib.npyio.NpzFile) -> list[PrunedBranchRecord]:
    reasons = npz["reasons"]
    distances = npz["distances"]
    coords_flat = npz["coords_flat"]
    coords_indptr = npz["coords_indptr"]
    records = []
    for i in range(len(reasons)):
        start, end = coords_indptr[i], coords_indptr[i + 1]
        records.append(
            PrunedBranchRecord(
                reason=str(reasons[i]),
                branch_distance=float(distances[i]),
                coords=coords_flat[start:end],
            )
        )
    return records


def save_analysis_cache(
    out_dir: Path,
    image_stem: str,
    *,
    skeleton_result: SkeletonResult,
    flaking_result: FlakingResult,
    stats_row: dict,
) -> Path:
    """Writes six files into out_dir / image_stem /. Returns that directory.
    Does NOT write overlay.png -- that's rendered separately (see
    overlay.render_crack_stats_overlay) since it needs the RGB source image,
    not just this cache's own arrays."""
    image_dir = out_dir / image_stem
    image_dir.mkdir(parents=True, exist_ok=True)

    with open(image_dir / "stats.json", "w") as f:
        json.dump(stats_row, f, indent=2)

    np.savez_compressed(image_dir / "mask_corrected.npz", mask=flaking_result.mask_corrected)
    np.savez_compressed(image_dir / "skeleton_final.npz", skeleton=skeleton_result.skel_image)
    np.savez_compressed(image_dir / "excluded_mask.npz", mask=flaking_result.excluded_mask)

    candidates_payload = {
        "reference_width_px": flaking_result.reference_width_px,
        "excluded_area_px2": flaking_result.excluded_area_px2,
        "excluded_area_pct": flaking_result.excluded_area_pct,
        "candidates": [
            {
                "label": c.label,
                "area_px2": c.area_px2,
                "solidity": c.solidity,
                "bbox": list(c.bbox),
            }
            for c in flaking_result.candidates
        ],
    }
    with open(image_dir / "flaking_candidates.json", "w") as f:
        json.dump(candidates_payload, f, indent=2)

    np.savez_compressed(
        image_dir / "pruned_branches.npz",
        **_pruned_branches_to_npz_arrays(skeleton_result.pruned_branches),
    )

    return image_dir


def load_analysis_cache(out_dir: Path, image_stem: str) -> AnalysisCache:
    image_dir = out_dir / image_stem

    with open(image_dir / "stats.json") as f:
        stats_row = json.load(f)

    mask_corrected = np.load(image_dir / "mask_corrected.npz")["mask"]
    skeleton_final = np.load(image_dir / "skeleton_final.npz")["skeleton"]
    excluded_mask = np.load(image_dir / "excluded_mask.npz")["mask"]

    with open(image_dir / "flaking_candidates.json") as f:
        candidates_payload = json.load(f)
    flaking_candidates = [
        FlakingCandidate(
            label=c["label"],
            area_px2=c["area_px2"],
            solidity=c["solidity"],
            bbox=tuple(c["bbox"]),
        )
        for c in candidates_payload["candidates"]
    ]

    with np.load(image_dir / "pruned_branches.npz", allow_pickle=True) as npz:
        pruned_branches = _pruned_branches_from_npz(npz)

    return AnalysisCache(
        stats_row=stats_row,
        mask_corrected=mask_corrected,
        skeleton_final=skeleton_final,
        excluded_mask=excluded_mask,
        flaking_candidates=flaking_candidates,
        reference_width_px=candidates_payload["reference_width_px"],
        excluded_area_px2=candidates_payload["excluded_area_px2"],
        excluded_area_pct=candidates_payload["excluded_area_pct"],
        pruned_branches=pruned_branches,
    )
