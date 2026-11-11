"""Smoke tests for the entry points (review finding 16): each one runs end to
end on a small synthetic image and writes what it promises. They check that
the code runs, not the numbers -- the library tests cover those. The broken
exporter import of October 2026 would have failed here.

The test image is a 3x3 grid with one flaked disk on its centre junction, so
the flaking path (edges touching the flaked region are omitted) runs too.
"""

import math
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from scripts.batch_stats import export_crack_stats
from src.crackgraph.region import default_corner_crop
from src.crackgraph.synthetic import generate_grid_with_flakes


@pytest.fixture
def flaked_grid_image(tmp_path: Path) -> Path:
    gray = generate_grid_with_flakes()
    path = tmp_path / "coating_x" / "synthetic_grid.png"
    path.parent.mkdir()
    Image.fromarray(np.clip(gray, 0, 255).astype(np.uint8)).save(path)
    return path


def _check_row(row: dict) -> None:
    assert row["image_filename"] == "synthetic_grid.png"
    assert row["scale_bar_check"] == export_crack_stats.SCALE_BAR_NOT_CHECKED
    assert row["flaking_n_candidates"] >= 1
    assert 0.0 < row["crack_area_pct"] < 100.0
    assert row["n_components"] >= 1
    assert 0.0 < row["giant_component_fraction"] <= 1.0
    assert not math.isnan(row["median_width_px"])


def test_export_compute_row_runs(flaked_grid_image: Path, tmp_path: Path):
    stages = []
    row = export_crack_stats.compute_row(flaked_grid_image, cache_dir=tmp_path / "cache", on_stage=stages.append)
    _check_row(row)
    assert row["flaking_n_edges_omitted"] >= 1
    assert row["runtime_total_s"] > 0
    assert stages == export_crack_stats.COMPUTE_ROW_STAGES
    assert (tmp_path / "cache" / "synthetic_grid" / "overlay.png").exists()


def test_analyze_image_full_pipeline_runs(flaked_grid_image: Path, tmp_path: Path, monkeypatch, capsys):
    from src import analyze_image

    out_dir = tmp_path / "out"
    xlsx = tmp_path / "runs.xlsx"
    monkeypatch.setattr(
        sys, "argv",
        ["analyze_image", str(flaked_grid_image), "--full-image",
         "--out-dir", str(out_dir), "--xlsx-out", str(xlsx)],
    )
    analyze_image.main()
    report = capsys.readouterr().out

    sub = out_dir / "coating_x"
    for suffix in ("overlay.png", "edge_metrics.csv"):
        assert (sub / f"synthetic_grid_full_{suffix}").exists(), suffix
    assert xlsx.exists()
    assert "Edge geometry: length/width/area" in report
    # The flake sits on a junction, so some edges touch it and must be reported
    # as removed before the graph analysis.
    assert "Skeleton edges touching a flaked region" in report


def test_overview_figure_runs(flaked_grid_image: Path, tmp_path: Path, monkeypatch):
    from scripts.spatial_overview import overview_figure

    out_dir = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", ["overview_figure", str(flaked_grid_image), "--out-dir", str(out_dir)])
    overview_figure.main()
    assert (out_dir / "coating_x" / "synthetic_grid_overview.png").exists()
    assert (out_dir / "report.html").exists()


def test_overview_figure_rejects_non_2x2_grid(flaked_grid_image: Path, monkeypatch):
    # Review finding 11: used to run the whole analysis, then crash drawing.
    from scripts.spatial_overview import overview_figure

    monkeypatch.setattr(sys, "argv", ["overview_figure", str(flaked_grid_image), "--n-rows", "4"])
    with pytest.raises(SystemExit):
        overview_figure.parse_args()


def test_default_corner_crop_geometry():
    region = default_corner_crop(7600, 7300)
    margin, crop = round(0.02 * 7300), round(0.125 * 7300)
    assert (region.row_slice.start, region.row_slice.stop) == (margin, margin + crop)
    assert (region.col_slice.start, region.col_slice.stop) == (margin, margin + crop)


def test_default_corner_crop_clamps_to_small_image():
    region = default_corner_crop(100, 2000)  # crop would run past the bottom edge
    assert region.row_slice.stop == 100
    assert region.row_slice.start <= region.row_slice.stop


def test_gui_starts_without_errors():
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(Path(__file__).resolve().parent.parent / "app.py"), default_timeout=60)
    app.run()
    assert not app.exception
