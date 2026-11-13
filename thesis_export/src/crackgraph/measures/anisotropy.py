"""Orientation anisotropy of the cracks in one region: whether they share
a preferred direction.

scan_orientations() takes local direction samples along every kept segment
once per image; measure_anisotropy() combines the samples that lie inside
the region. Samples are local, so they are assigned by their own position,
not by their segment's middle. Method:
docs/walkthrough/08_curvature_anisotropy.md.

A low index doesn't rule out two perpendicular crack families (a grid):
the index can't tell that apart from random directions. Check the rose
plot for two peaks before calling a pattern isotropic.
"""

from src.crackgraph.anisotropy import AnisotropyResult, OrientationSample, anisotropy_from_samples, compute_orientation_samples
from src.crackgraph.engine import EngineResult
from src.crackgraph.regions import Region
from src.crackgraph.settings import AnalysisSettings


def scan_orientations(engine: EngineResult, settings: AnalysisSettings) -> list[OrientationSample]:
    samples = compute_orientation_samples(
        engine.skeleton.skeleton, engine.graph, window_px=settings.orientation_window_px,
    )
    return [s for s in samples if s.path_index not in engine.omitted]


def anisotropy_in_region(
    samples: list[OrientationSample], region: Region, settings: AnalysisSettings
) -> AnisotropyResult:
    local = [s for s in samples if region.contains_point(s.row, s.col)]
    return anisotropy_from_samples(local, window_px=settings.orientation_window_px)


def measure_anisotropy(result: AnisotropyResult) -> dict:
    return {
        "anisotropy_index": result.anisotropy_index,
        # Not meaningful when the index is near 0 (no preferred direction).
        "dominant_bearing_deg": result.dominant_bearing_deg,
        "anisotropy_n_samples": result.n_samples,
    }
