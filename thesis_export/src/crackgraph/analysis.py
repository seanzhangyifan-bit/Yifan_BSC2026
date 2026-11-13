"""One analysis run: an image and its settings in, one row per region out.

    image --> engine (once) --> regions --> measurements --> rows

This is the single entry point the GUI (app.py) and the command line
(src/analyze.py) both call. See settings.py for what a user can change.
"""

import dataclasses
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

from src.crackgraph.anisotropy import AnisotropyResult
from src.crackgraph.curvature import CurvatureScanResult
from src.crackgraph.engine import ENGINE_STAGES, EngineResult, run_engine
from src.crackgraph.io_utils import load_image
from src.crackgraph.measures.anisotropy import anisotropy_in_region, measure_anisotropy, scan_orientations
from src.crackgraph.measures.crack_stats import measure_crack_stats
from src.crackgraph.measures.segments import segment_rows
from src.crackgraph.measures.tortuosity import curvature_in_region, measure_tortuosity, scan_curvature
from src.crackgraph.regions import Region
from src.crackgraph.settings import AnalysisSettings

def analysis_stages(settings: AnalysisSettings) -> list[str]:
    """Progress labels analyze_image reports, in order, for these settings,
    so a caller can size a progress bar before the run starts."""
    stages = list(ENGINE_STAGES)
    if "tortuosity" in settings.measurements:
        stages.append("Curvature & tortuosity")
    if "anisotropy" in settings.measurements:
        stages.append("Anisotropy")
    stages.append("Measuring regions")
    return stages


@dataclass
class ImageAnalysis:
    image_path: Path
    settings: AnalysisSettings
    rgb: np.ndarray
    engine: EngineResult
    regions: list[Region]
    rows: list[dict]  # one per region
    # Whole-image connectivity, filled only when connectivity was asked for
    # and the regions aren't the whole image (region rows then leave it out).
    image_connectivity: dict | None = None
    segments: list[dict] = field(default_factory=list)  # only if "segments" was requested
    # Per-region intermediate results, kept for the figures (rose plots,
    # tortuosity histograms); keyed by region label.
    anisotropy: dict[str, AnisotropyResult] = field(default_factory=dict)
    curvature: dict[str, CurvatureScanResult] = field(default_factory=dict)


def analyze_image(
    image_path: Path,
    settings: AnalysisSettings,
    *,
    on_stage: Callable[[str], None] | None = None,
) -> ImageAnalysis:
    report = on_stage or (lambda _stage: None)
    t_start = time.perf_counter()
    image_path = Path(image_path)
    gray, rgb = load_image(image_path)
    height, width = gray.shape

    engine = run_engine(gray, settings, on_stage=report)
    regions = settings.regions.regions(height, width)

    curvature_scan = None
    if "tortuosity" in settings.measurements:
        t0 = time.perf_counter()
        curvature_scan = scan_curvature(engine, settings)
        engine.runtimes_s["curvature"] = time.perf_counter() - t0
        report("Curvature & tortuosity")
    orientation_samples = None
    if "anisotropy" in settings.measurements:
        t0 = time.perf_counter()
        orientation_samples = scan_orientations(engine, settings)
        engine.runtimes_s["anisotropy"] = time.perf_counter() - t0
        report("Anisotropy")

    result = ImageAnalysis(image_path=image_path, settings=settings, rgb=rgb, engine=engine, regions=regions, rows=[])
    t0 = time.perf_counter()
    for region in regions:
        row = {
            "image_filename": image_path.name,
            "source_folder": image_path.parent.name,
            "region": region.label,
            "region_rows_px": f"{region.row_start}-{region.row_stop}",
            "region_cols_px": f"{region.col_start}-{region.col_stop}",
            "region_area_pct": 100.0 * region.area_px / (height * width),
            "image_width_px": width,
            "image_height_px": height,
        }
        if "crack_stats" in settings.measurements:
            row.update(measure_crack_stats(engine, region, settings))
        if curvature_scan is not None:
            result.curvature[region.label] = curvature_in_region(curvature_scan, engine, region)
            row.update(measure_tortuosity(curvature_scan, engine, region, settings))
        if orientation_samples is not None:
            aniso = anisotropy_in_region(orientation_samples, region, settings)
            result.anisotropy[region.label] = aniso
            row.update(measure_anisotropy(aniso))
        if "segments" in settings.measurements:
            for seg in segment_rows(engine, region, settings):
                result.segments.append({"image_filename": image_path.name, "region": region.label, **seg})
        result.rows.append(row)
    wants_connectivity = (
        "crack_stats" in settings.measurements and "connectivity" in settings.crack_stats_groups
    )
    if wants_connectivity and not any(r.is_whole_image(engine.shape) for r in regions):
        whole = Region("whole", 0, height, 0, width)
        whole_settings = dataclasses.replace(settings, crack_stats_groups=("connectivity",))
        result.image_connectivity = {
            "image_filename": image_path.name,
            "source_folder": image_path.parent.name,
            **measure_crack_stats(engine, whole, whole_settings),
        }
    engine.runtimes_s["measure_regions"] = time.perf_counter() - t0
    engine.runtimes_s["total"] = time.perf_counter() - t_start
    report("Measuring regions")

    if settings.include_runtime:
        # Runtimes are per image: every region row of one image repeats them.
        for row in result.rows:
            row.update({f"runtime_{k}_s": v for k, v in engine.runtimes_s.items()})
    return result
