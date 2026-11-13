"""Checks for the unified analysis (settings -> engine -> regions -> measures).

The main guarantee: with default settings and the whole image, the crack
stats equal the old exporter's exactly, so the thesis numbers don't move.
The old exporter (scripts/batch_stats/export_crack_stats.py, archived
2026-11-13) was run once on the synthetic flaked grid; its output is frozen
in tests/fixtures/old_exporter_flaked_grid.json. Also: grid cells add up to the whole image,
connectivity stays whole-image only, and µm/px converts the two physical
thresholds as stated.
"""

import json
import math
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from src.crackgraph.analysis import analyze_image
from src.crackgraph.regions import RegionSpec, grid_cells
from src.crackgraph.settings import DEFAULT_UM_PER_PX, AnalysisSettings
from src.crackgraph.synthetic import generate_grid_with_flakes


@pytest.fixture(scope="module")
def flaked_image(tmp_path_factory):
    img = np.asarray(generate_grid_with_flakes()).astype(np.uint8)
    path = tmp_path_factory.mktemp("img") / "flaked.png"
    Image.fromarray(img).convert("RGB").save(path)
    return path


OLD_EXPORTER = Path(__file__).parent / "fixtures" / "old_exporter_flaked_grid.json"


def _same(a, b):
    if a is None:  # NaN is stored as null in the JSON
        return isinstance(b, float) and math.isnan(b)
    return a == pytest.approx(b, rel=1e-12, abs=1e-12)


def test_whole_image_matches_old_exporter(flaked_image):
    old = json.loads(OLD_EXPORTER.read_text())["row"]
    new = analyze_image(flaked_image, AnalysisSettings()).rows[0]
    for key, value in old.items():
        assert _same(value, new[key]), key


def test_default_calibration_gives_thesis_pixel_thresholds():
    s = AnalysisSettings()
    assert s.spur_px == 15
    assert s.dark_speck_area_px == 130


def test_thresholds_follow_calibration():
    s = AnalysisSettings(um_per_px=DEFAULT_UM_PER_PX / 2)  # twice the magnification
    assert s.spur_px == pytest.approx(30)
    assert s.dark_speck_area_px == 520


def test_grid_cells_cover_image_exactly():
    cells = grid_cells(101, 77, 3, 4)
    covered = np.zeros((101, 77), int)
    for c in cells:
        covered[c.row_slice, c.col_slice] += 1
    assert (covered == 1).all()
    assert [c.label.split()[1] for c in cells] == [str(i) for i in range(1, 13)]


def test_grid_crack_area_adds_up_and_connectivity_is_whole_image_only(flaked_image):
    whole = analyze_image(flaked_image, AnalysisSettings()).rows[0]
    grid = analyze_image(flaked_image, AnalysisSettings(regions=RegionSpec(mode="grid", n_rows=3, n_cols=3)))
    total = sum(r["crack_area_pct"] * r["region_area_pct"] / 100 for r in grid.rows)
    assert total == pytest.approx(whole["crack_area_pct"], rel=1e-12)
    assert all("n_components" not in r for r in grid.rows)
    assert grid.image_connectivity["n_components"] == whole["n_components"]


def test_selected_cells_only(flaked_image):
    spec = RegionSpec(mode="grid", n_rows=3, n_cols=3, cells=(1, 4, 7))
    rows = analyze_image(flaked_image, AnalysisSettings(regions=spec)).rows
    assert [r["region"] for r in rows] == ["cell 1 (r1c1)", "cell 4 (r2c1)", "cell 7 (r3c1)"]


def test_bad_cell_number_rejected():
    with pytest.raises(ValueError):
        RegionSpec(mode="grid", n_rows=2, n_cols=2, cells=(5,))


def test_column_groups_select_columns(flaked_image):
    row = analyze_image(flaked_image, AnalysisSettings(crack_stats_groups=("area",))).rows[0]
    assert "crack_area_pct" in row
    assert "median_width_px" not in row and "n_components" not in row
