"""Tortuosity (arc length / straight-line length) and curvature of the
crack segments in one region.

scan_curvature() measures every segment once per image; measure_tortuosity()
then summarises the segments whose middle pixel lies in the region, the
same rule crack stats use for segment counts. Segments touching a flaked
region are left out. Method: docs/walkthrough/07_curvature_anisotropy.md.
"""

import numpy as np

from src.crackgraph.curvature import CurvatureScanResult, compute_edge_curvature, reliable_tortuosities
from src.crackgraph.engine import EngineResult
from src.crackgraph.regions import Region
from src.crackgraph.settings import AnalysisSettings


def scan_curvature(engine: EngineResult, settings: AnalysisSettings) -> CurvatureScanResult:
    return compute_edge_curvature(
        engine.skeleton.skeleton, engine.graph, window_px=settings.curvature_window_px,
    )


def curvature_in_region(scan: CurvatureScanResult, engine: EngineResult, region: Region) -> CurvatureScanResult:
    """The same scan, restricted to kept segments whose middle pixel is in the region."""
    edges = [
        e for e in scan.edges
        if e.path_index not in engine.omitted and region.contains_point(*engine.path_midpoint(e.path_index))
    ]
    return CurvatureScanResult(edges=edges, n_edges_scanned=len(edges), window_px=scan.window_px)


def measure_tortuosity(
    scan: CurvatureScanResult, engine: EngineResult, region: Region, settings: AnalysisSettings
) -> dict:
    local = curvature_in_region(scan, engine, region)
    tort = reliable_tortuosities(local)
    kappa = [e.mean_abs_curvature_px_inv for e in local.edges if e.mean_abs_curvature_px_inv is not None]
    nan = float("nan")
    curvature_mean_px = float(np.mean(kappa)) if kappa else nan
    curvature_max_px = float(np.max(kappa)) if kappa else nan
    return {
        "tortuosity_mean": float(np.mean(tort)) if tort else nan,
        "tortuosity_median": float(np.median(tort)) if tort else nan,
        "tortuosity_n_segments": len(tort),
        # Curvature in 1/px divides by um_per_px to give 1/µm.
        "curvature_mean_per_um": curvature_mean_px / settings.um_per_px,
        "curvature_max_per_um": curvature_max_px / settings.um_per_px,
        "curvature_n_segments": len(kappa),
    }
