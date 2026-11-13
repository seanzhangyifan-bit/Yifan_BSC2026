"""Which parts of an image to report on: the whole image, its centre, or
cells of an N x M grid.

The pipeline runs once on the whole image; a region only decides which
part of that one result a row of numbers describes (see measures/). So a
grid's cells are measured with the same threshold and the same flaking
reference as the whole image, and their crack areas add up to its total.

Grid cells are numbered 1 to N*M, row by row from the top left. Cell
boundaries are spread evenly, so leftover pixels go to several cells
instead of all landing in the last row or column.
"""

from dataclasses import dataclass

import numpy as np

REGION_MODES = ("whole", "centre", "grid")


@dataclass(frozen=True)
class Region:
    label: str  # "whole", "centre" or "cell 5 (r2c2)"
    row_start: int
    row_stop: int
    col_start: int
    col_stop: int

    @property
    def row_slice(self) -> slice:
        return slice(self.row_start, self.row_stop)

    @property
    def col_slice(self) -> slice:
        return slice(self.col_start, self.col_stop)

    @property
    def area_px(self) -> int:
        return (self.row_stop - self.row_start) * (self.col_stop - self.col_start)

    def is_whole_image(self, shape: tuple[int, int]) -> bool:
        return (self.row_start, self.row_stop, self.col_start, self.col_stop) == (0, shape[0], 0, shape[1])

    def contains_point(self, row: float, col: float) -> bool:
        return self.row_start <= row < self.row_stop and self.col_start <= col < self.col_stop

    def contains(self, rows: np.ndarray, cols: np.ndarray) -> np.ndarray:
        """Boolean array: which of the (row, col) pixel positions lie inside."""
        return (
            (rows >= self.row_start) & (rows < self.row_stop)
            & (cols >= self.col_start) & (cols < self.col_stop)
        )


@dataclass(frozen=True)
class RegionSpec:
    """What the user asked for, independent of any one image's size.

    mode "whole": the whole image.
    mode "centre": a centred rectangle, centre_frac of the image's width
        and height (0.5 = the middle half along each side).
    mode "grid": an n_rows x n_cols grid; cells lists which cells to report
        (1-based, row by row), or None for every cell.
    """

    mode: str = "whole"
    centre_frac: float = 0.5
    n_rows: int = 2
    n_cols: int = 2
    cells: tuple[int, ...] | None = None

    def __post_init__(self):
        if self.mode not in REGION_MODES:
            raise ValueError(f"region mode must be one of {REGION_MODES}, got {self.mode!r}")
        if not 0 < self.centre_frac <= 1:
            raise ValueError(f"centre_frac must be in (0, 1], got {self.centre_frac}")
        if self.n_rows < 1 or self.n_cols < 1:
            raise ValueError("a grid needs at least 1 row and 1 column")
        if self.cells is not None:
            bad = [c for c in self.cells if not 1 <= c <= self.n_rows * self.n_cols]
            if bad:
                raise ValueError(
                    f"cells {bad} don't exist in a {self.n_rows}x{self.n_cols} grid "
                    f"(cells are numbered 1 to {self.n_rows * self.n_cols})"
                )

    def describe(self) -> str:
        if self.mode == "whole":
            return "whole image"
        if self.mode == "centre":
            return f"centre, {self.centre_frac:g} of width and height"
        which = "all cells" if self.cells is None else "cells " + ",".join(map(str, self.cells))
        return f"{self.n_rows}x{self.n_cols} grid, {which}"

    def regions(self, height: int, width: int) -> list[Region]:
        if self.mode == "whole":
            return [Region("whole", 0, height, 0, width)]
        if self.mode == "centre":
            h = round(height * self.centre_frac)
            w = round(width * self.centre_frac)
            r0 = (height - h) // 2
            c0 = (width - w) // 2
            return [Region("centre", r0, r0 + h, c0, c0 + w)]
        return grid_cells(height, width, self.n_rows, self.n_cols, self.cells)


def grid_cells(
    height: int, width: int, n_rows: int, n_cols: int, cells: tuple[int, ...] | None = None
) -> list[Region]:
    """The chosen cells of an n_rows x n_cols grid that covers the image
    edge to edge, in cell-number order."""
    row_bounds = [round(i * height / n_rows) for i in range(n_rows + 1)]
    col_bounds = [round(j * width / n_cols) for j in range(n_cols + 1)]
    wanted = set(cells) if cells is not None else None
    out = []
    for i in range(n_rows):
        for j in range(n_cols):
            number = i * n_cols + j + 1
            if wanted is not None and number not in wanted:
                continue
            out.append(
                Region(
                    f"cell {number} (r{i + 1}c{j + 1})",
                    row_bounds[i], row_bounds[i + 1], col_bounds[j], col_bounds[j + 1],
                )
            )
    return out


def corner_crop(height: int, width: int, *, corner_frac: float = 0.125, edge_margin_frac: float = 0.02) -> Region:
    """A square crop near the top-left corner, inset from the image edges.
    Both sizes are fractions of the image width. Only the validation sweeps
    (scripts/validation/) use this, so their results stay comparable with
    earlier runs; it is not one of the user-facing region modes."""
    margin = round(edge_margin_frac * width)
    size = round(corner_frac * width)
    row_end = min(margin + size, height)
    col_end = min(margin + size, width)
    return Region("corner", min(margin, row_end), row_end, min(margin, col_end), col_end)
