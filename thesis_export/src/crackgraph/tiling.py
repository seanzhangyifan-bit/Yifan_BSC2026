"""Coarse N x M grid tiling of a full image into non-overlapping sections,
for the multi-section overview figure (scripts/overview_figure.py).

Deliberately separate from region.py's default_corner_crop: that is the
pipeline's single validated analysis window (corner_frac of image width,
inset from the true edges by edge_margin_frac). This tiling is a different,
coarser concern -- covering the *entire* image in a handful of sections to
see how anisotropy/curvature vary spatially -- and does not apply
edge_margin_frac at all: every pixel, edge to edge, is assigned to exactly
one tile.
"""

from dataclasses import dataclass


@dataclass
class Tile:
    row_slice: slice
    col_slice: slice
    row_idx: int
    col_idx: int
    n_rows: int
    n_cols: int

    @property
    def label(self) -> str:
        return f"section r{self.row_idx}c{self.col_idx}"


def grid_tiles(height: int, width: int, n_rows: int, n_cols: int) -> list[Tile]:
    """Partition [0,height) x [0,width) into n_rows x n_cols tiles that
    exactly cover the image with no gaps or overlap, in row-major order.

    Boundaries are computed as round(i * height / n_rows) (and similarly
    for width/n_cols) so that when the image doesn't divide evenly, the
    leftover pixels are spread across tiles rather than all dumped into the
    last row/column.
    """
    row_bounds = [round(i * height / n_rows) for i in range(n_rows + 1)]
    col_bounds = [round(j * width / n_cols) for j in range(n_cols + 1)]
    tiles = []
    for i in range(n_rows):
        for j in range(n_cols):
            tiles.append(
                Tile(
                    row_slice=slice(row_bounds[i], row_bounds[i + 1]),
                    col_slice=slice(col_bounds[j], col_bounds[j + 1]),
                    row_idx=i,
                    col_idx=j,
                    n_rows=n_rows,
                    n_cols=n_cols,
                )
            )
    return tiles
