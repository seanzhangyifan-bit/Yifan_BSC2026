"""Write a run's results to one spreadsheet and its figures to PNGs.

Workbook sheets:
- regions: one row per (image, region), the columns the user chose.
- image_connectivity: whole-image connectivity, only when connectivity was
  asked for and the regions aren't the whole image.
- segments: the per-segment table, only if requested.
- settings: every setting the run used, so the numbers can be reproduced.
- labels: image -> group, only when the GUI's grouping board was used.
"""

from pathlib import Path

import pandas as pd

from .analysis import ImageAnalysis
from .figures import render_overlay_with_regions, render_region_map, render_region_panels
from .settings import AnalysisSettings, settings_record

FIGURES = ("overlay", "panels", "map")


def results_tables(analyses: list[ImageAnalysis]) -> dict[str, pd.DataFrame]:
    tables = {"regions": pd.DataFrame([row for a in analyses for row in a.rows])}
    connectivity = [a.image_connectivity for a in analyses if a.image_connectivity is not None]
    if connectivity:
        tables["image_connectivity"] = pd.DataFrame(connectivity)
    segments = [s for a in analyses for s in a.segments]
    if segments:
        tables["segments"] = pd.DataFrame(segments)
    return tables


def write_workbook(
    analyses: list[ImageAnalysis], settings: AnalysisSettings, out_path: Path,
    labels: pd.DataFrame | None = None,
) -> None:
    """labels: optional image_filename -> group table from the GUI's grouping
    board (src/crackgraph/grouping.py), written as a "labels" sheet."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    record = settings_record(settings)
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        for name, df in results_tables(analyses).items():
            df.to_excel(writer, sheet_name=name, index=False)
        if labels is not None and not labels.empty:
            labels.to_excel(writer, sheet_name="labels", index=False)
        pd.DataFrame({"setting": list(record), "value": [str(v) for v in record.values()]}).to_excel(
            writer, sheet_name="settings", index=False,
        )


def write_figures(
    analysis: ImageAnalysis, out_dir: Path, figures: tuple[str, ...], map_column: str
) -> list[Path]:
    """The requested figures for one image, under out_dir/<source folder>/.
    Returns the paths actually written (a figure with nothing to show is skipped)."""
    folder = out_dir / analysis.image_path.parent.name
    folder.mkdir(parents=True, exist_ok=True)
    stem = analysis.image_path.stem
    written = []
    if "overlay" in figures:
        path = folder / f"{stem}_overlay.png"
        render_overlay_with_regions(analysis, path)
        written.append(path)
    if "panels" in figures:
        path = folder / f"{stem}_panels.png"
        if render_region_panels(analysis, path):
            written.append(path)
    if "map" in figures and len(analysis.regions) > 1:
        path = folder / f"{stem}_map_{map_column}.png"
        if render_region_map(analysis, map_column, path):
            written.append(path)
    return written
