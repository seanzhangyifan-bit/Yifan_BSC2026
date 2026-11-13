"""The shared engine: binarize -> skeletonize -> flaking exclusion -> graph.

run_engine() runs these once on a whole image. Every measurement in
measures/ reads its EngineResult and reports on one region of it, so
crack stats, tortuosity and anisotropy always describe the same skeleton.

Flaking: the mask is skeletonized once. Edges with a pixel inside a flaked
region are listed in `omitted`; every measurement leaves them out, so
nothing is measured in, or connects through, a region with no evidence
about cracks (see docs/walkthrough/03_flaking.md).
"""

import time
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from src.crackgraph.binarize import BinarizeResult, binarize
from src.crackgraph.flaking import FlakingResult, exclude_flaking_regions, flake_touching_path_indices
from src.crackgraph.graph import GraphResult, extract_graph, path_pixel_indices
from src.crackgraph.settings import AnalysisSettings
from src.crackgraph.skeleton import SkeletonResult, skeletonize_and_prune

# Progress labels, in the order run_engine reports them through on_stage.
ENGINE_STAGES = ("Binarizing", "Skeletonizing", "Checking for flaking", "Extracting graph")


@dataclass
class EngineResult:
    shape: tuple[int, int]  # (height, width) of the whole image
    binarize: BinarizeResult
    skeleton: SkeletonResult
    flaking: FlakingResult
    graph: GraphResult
    omitted: set[int]  # path indices of edges touching a flaked region
    runtimes_s: dict[str, float]
    _pixels: dict[int, tuple[np.ndarray, np.ndarray]] = field(default_factory=dict, repr=False)

    @property
    def kept_paths(self) -> list[int]:
        """Path indices of every edge not touching a flaked region."""
        return [int(i) for i in self.graph.summary.index if i not in self.omitted]

    def path_pixels(self, path_index: int) -> tuple[np.ndarray, np.ndarray]:
        """(rows, cols) integer pixel positions along one edge, cached."""
        if path_index not in self._pixels:
            coords = self.skeleton.skeleton.path_coordinates(int(path_index))
            self._pixels[path_index] = path_pixel_indices(coords, self.shape)
        return self._pixels[path_index]

    def path_midpoint(self, path_index: int) -> tuple[int, int]:
        """The middle pixel of an edge. An edge belongs to the region holding
        its midpoint, so each edge is counted in exactly one grid cell."""
        rr, cc = self.path_pixels(path_index)
        k = len(rr) // 2
        return int(rr[k]), int(cc[k])


def run_engine(
    gray: np.ndarray,
    settings: AnalysisSettings,
    on_stage: Callable[[str], None] | None = None,
) -> EngineResult:
    report = on_stage or (lambda _stage: None)
    runtimes = {}

    t0 = time.perf_counter()
    binarize_result = binarize(gray)
    runtimes["binarize"] = time.perf_counter() - t0
    report(ENGINE_STAGES[0])

    t0 = time.perf_counter()
    skeleton_result = skeletonize_and_prune(
        binarize_result.mask,
        source_image=gray,
        spur_px=settings.spur_px,
        dark_speck_area_px=settings.dark_speck_area_px,
    )
    runtimes["skeletonize"] = time.perf_counter() - t0
    report(ENGINE_STAGES[1])

    t0 = time.perf_counter()
    flaking_result = exclude_flaking_regions(
        skeleton_result.mask_clean, skeleton_result.skel_image, skeleton_result.medial_radius,
    )
    runtimes["flaking"] = time.perf_counter() - t0
    report(ENGINE_STAGES[2])

    t0 = time.perf_counter()
    graph_result = extract_graph(skeleton_result.skeleton)
    runtimes["graph_extract"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    omitted = flake_touching_path_indices(
        skeleton_result.skeleton, graph_result, flaking_result.excluded_mask,
    )
    runtimes["flaking"] += time.perf_counter() - t0
    report(ENGINE_STAGES[3])

    return EngineResult(
        shape=gray.shape,
        binarize=binarize_result,
        skeleton=skeleton_result,
        flaking=flaking_result,
        graph=graph_result,
        omitted=set(int(i) for i in omitted),
        runtimes_s=runtimes,
    )
