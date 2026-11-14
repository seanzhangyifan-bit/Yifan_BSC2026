"""Group images for comparison: which image belongs to which condition.

The GUI's grouping board (src/crackgraph/gui/) produces an assignment
    {image_filename: (row_value, column_value) or None}
where None means "left out". This module turns that into a labels table,
guesses an assignment from file names, and draws the replicates plot.

Rows and columns are the two factors the user varies (e.g. ink x blade gap);
images in the same cell are replicates. Labels are [user-assigned]: the tool
never checks them against the images.
"""

import re

import matplotlib.pyplot as plt
import pandas as pd

Assignment = dict[str, "tuple[str, str] | None"]


def name_parts(filename: str) -> set[str]:
    """Lower-case parts of a file name, split at non-alphanumerics and at
    letter/digit changes: "inkA_gap100_v2.tif" -> {inka, gap, 100, v, 2, tif}."""
    parts = set()
    for chunk in re.split(r"[^0-9A-Za-z]+", filename):
        parts.update(p.lower() for p in re.findall(r"[A-Za-z]+|[0-9]+", chunk))
        if chunk:
            parts.add(chunk.lower())
    return parts


def presort_by_name(
    filenames: list[str], rows: list[str], cols: list[str], match_rows: bool = True,
) -> Assignment:
    """Guess each image's cell from its file name.

    A value matches when it equals a whole name part (see name_parts), case
    ignored. An image is placed only when exactly one row value and exactly
    one column value match; anything ambiguous or unmatched is left out
    (None), for the user to place by hand. Deliberately conservative.

    match_rows=False is for a board with one row (only columns vary): every
    matched image goes to rows[0].
    """
    out: Assignment = {}
    for name in filenames:
        parts = name_parts(name)
        row_hits = [r for r in rows if r.strip().lower() in parts] if match_rows else rows[:1]
        col_hits = [c for c in cols if c.strip().lower() in parts]
        out[name] = (row_hits[0], col_hits[0]) if len(row_hits) == 1 and len(col_hits) == 1 else None
    return out


def labels_table(
    assignment: Assignment, row_factor: str, col_factor: str,
    rows: list[str], cols: list[str], order: list[str] | None = None,
) -> pd.DataFrame:
    """One row per placed image: image_filename, <row_factor>, <col_factor>, replicate.

    Replicates are numbered 1, 2, ... within each cell, in `order` (default:
    file name order). Images placed in a row or column no longer on the board
    are dropped.
    """
    names = order if order is not None else sorted(assignment)
    records, counts = [], {}
    for name in names:
        cell = assignment.get(name)
        if cell is None or cell[0] not in rows or cell[1] not in cols:
            continue
        counts[cell] = counts.get(cell, 0) + 1
        records.append({"image_filename": name, row_factor: cell[0], col_factor: cell[1],
                        "replicate": counts[cell]})
    return pd.DataFrame(records, columns=["image_filename", row_factor, col_factor, "replicate"])


def plot_replicates(
    ax, table: pd.DataFrame, metric: str, x: str, colour: str,
    x_order: list[str], colour_order: list[str], colours: list[str] | None = None,
) -> None:
    """Dot per image, grouped along x by `x` and coloured by `colour`.

    A mean bar is drawn only for groups with at least 2 images; n is printed
    under every group, in red when n = 1 (no replicate spread to compare
    against). NaN metric values are skipped and not counted.
    """
    colours = colours or plt.rcParams["axes.prop_cycle"].by_key()["color"]
    n_c = max(len(colour_order), 1)
    width = 0.7
    step = width / n_c
    for j, c in enumerate(colour_order):
        col = colours[j % len(colours)]
        labelled = False
        for i, xv in enumerate(x_order):
            vals = table.loc[(table[x] == xv) & (table[colour] == c), metric].dropna().to_numpy(float)
            if len(vals) == 0:
                continue
            centre = i - width / 2 + step * (j + 0.5)
            spread = min(step * 0.6, 0.18)
            offsets = [0.0] if len(vals) == 1 else [
                -spread / 2 + spread * k / (len(vals) - 1) for k in range(len(vals))
            ]
            ax.scatter([centre + o for o in offsets], vals, s=22, color=col, zorder=3,
                       label=None if labelled else c)
            labelled = True
            if len(vals) >= 2:
                ax.hlines(vals.mean(), centre - step * 0.4, centre + step * 0.4, color=col, lw=2, zorder=2)
            ax.annotate(f"n={len(vals)}", (centre, 0), xycoords=("data", "axes fraction"),
                        xytext=(0, 3), textcoords="offset points", ha="center", va="bottom",
                        fontsize=7, color="#b23b3b" if len(vals) < 2 else "0.4")
    ax.set_xticks(range(len(x_order)), x_order)
    ax.set_xlim(-0.6, len(x_order) - 0.4)
    ax.set_xlabel(x)
    ax.set_ylabel(metric)
    if len(colour_order) > 1 and ax.get_legend_handles_labels()[1]:
        ax.legend(title=colour, fontsize=8, title_fontsize=8, frameon=False)
