"""The two ways to run the analysis, end to end: the command line
(src/analyze.py) and the GUI (app.py), on a small synthetic image."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from PIL import Image

from src import analyze
from src.crackgraph.synthetic import generate_grid_with_flakes


@pytest.fixture(scope="module")
def image(tmp_path_factory):
    path = tmp_path_factory.mktemp("img") / "flaked.png"
    Image.fromarray(np.asarray(generate_grid_with_flakes()).astype(np.uint8)).convert("RGB").save(path)
    return path


def test_cli_grid_run_writes_every_sheet_and_figure(image, tmp_path):
    out = tmp_path / "out"
    analyze.main([
        str(image), "--out-dir", str(out), "--regions", "grid", "--grid", "2x2", "--cells", "1,4",
        "--measure", "crack_stats", "tortuosity", "anisotropy", "segments",
        "--figures", "overlay", "panels", "map",
    ])
    sheets = pd.read_excel(out / "results.xlsx", sheet_name=None)
    assert set(sheets) == {"regions", "image_connectivity", "segments", "settings"}
    assert list(sheets["regions"]["region"]) == ["cell 1 (r1c1)", "cell 4 (r2c2)"]
    for suffix in ("overlay", "panels", "map_crack_area_pct"):
        assert (out / image.parent.name / f"{image.stem}_{suffix}.png").exists()


def test_cli_rejects_a_cell_outside_the_grid(image, tmp_path):
    with pytest.raises(ValueError):
        analyze.main([str(image), "--out-dir", str(tmp_path), "--regions", "grid", "--grid", "2x2", "--cells", "9"])


def test_gui_loads_without_errors():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(Path(__file__).parent.parent / "app.py"), default_timeout=30).run()
    assert not at.exception
    at.radio[0].set_value("grid").run()
    assert not at.exception
