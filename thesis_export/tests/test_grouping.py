"""Grouping board logic (src/crackgraph/grouping.py): file-name pre-sort,
labels table, replicates plot. The board's drag-and-drop frontend itself
is not tested here (it runs in the browser)."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.crackgraph.grouping import labels_table, name_parts, plot_replicates, presort_by_name  # noqa: E402

NAMES = [
    "inkA_gap50_v1.tif", "inkA_gap50_v2.tif", "IMG_0412.jpg",
    "B-100-rep1.png", "A_B_100.jpg", "sample A 50.tif",
]


def test_name_parts_split_at_separators_and_letter_digit_changes():
    assert {"inka", "gap", "50", "v", "1", "tif", "gap50"} <= name_parts("inkA_gap50_v1.tif")
    assert {"b", "100", "rep", "1"} <= name_parts("B-100-rep1.png")


def test_presort_places_only_unambiguous_names():
    got = presort_by_name(NAMES, rows=["inkA", "B", "A"], cols=["50", "100"])
    assert got["inkA_gap50_v1.tif"] == ("inkA", "50")
    assert got["B-100-rep1.png"] == ("B", "100")
    assert got["sample A 50.tif"] == ("A", "50")
    assert got["IMG_0412.jpg"] is None          # nothing readable
    assert got["A_B_100.jpg"] is None           # two row values match: ambiguous


def test_presort_single_row_matches_columns_only():
    got = presort_by_name(["x_50.tif", "y_75.tif"], rows=["all"], cols=["50", "100"], match_rows=False)
    assert got == {"x_50.tif": ("all", "50"), "y_75.tif": None}


def test_presort_does_not_match_inside_a_longer_number():
    assert presort_by_name(["gap150.tif"], ["all"], ["50"], match_rows=False)["gap150.tif"] is None


def test_labels_table_numbers_replicates_per_cell_and_drops_unplaced():
    assignment = {"a.tif": ("A", "50"), "b.tif": ("A", "50"), "c.tif": ("B", "50"), "d.tif": None,
                  "e.tif": ("C", "50")}  # row C no longer on the board
    t = labels_table(assignment, "ink", "gap", rows=["A", "B"], cols=["50"], order=list(assignment))
    assert list(t.columns) == ["image_filename", "ink", "gap", "replicate"]
    assert t["image_filename"].tolist() == ["a.tif", "b.tif", "c.tif"]
    assert t["replicate"].tolist() == [1, 2, 1]


def test_labels_table_empty_has_columns():
    t = labels_table({"a.tif": None}, "ink", "gap", ["A"], ["50"])
    assert t.empty and list(t.columns) == ["image_filename", "ink", "gap", "replicate"]


def _plot(table):
    fig, ax = plt.subplots()
    plot_replicates(ax, table, "w", "gap", "ink", ["50", "100"], ["A", "B"])
    return fig, ax


def test_plot_draws_mean_bar_only_with_two_or_more_images():
    table = pd.DataFrame({
        "image_filename": list("abc"), "ink": ["A", "A", "B"], "gap": ["50", "50", "100"],
        "w": [1.0, 3.0, 2.0],
    })
    fig, ax = _plot(table)
    bars = ax.collections[1:]  # scatter, hlines, scatter
    means = [c for c in ax.collections if c.__class__.__name__ == "LineCollection"]
    assert len(means) == 1
    np.testing.assert_allclose(means[0].get_segments()[0][:, 1], [2.0, 2.0])
    texts = sorted(t.get_text() for t in ax.texts)
    assert texts == ["n=1", "n=2"]
    assert bars  # something drawn
    plt.close(fig)


def test_plot_skips_nan_values():
    table = pd.DataFrame({"image_filename": list("ab"), "ink": ["A", "A"], "gap": ["50", "50"],
                          "w": [1.0, np.nan]})
    fig, ax = _plot(table)
    assert [t.get_text() for t in ax.texts] == ["n=1"]
    plt.close(fig)
