"""grid_tiles must exactly cover the image (no gaps, no overlap, every
pixel assigned to exactly one tile) even when the image doesn't divide
evenly by n_rows/n_cols, and produce unique labels."""

import numpy as np
import pytest

from src.crackgraph.tiling import grid_tiles


@pytest.mark.parametrize(
    "height,width,n_rows,n_cols",
    [
        (100, 100, 4, 4),
        (100, 100, 3, 3),  # doesn't divide evenly
        (97, 133, 5, 7),  # neither dimension divides evenly
        (10, 10, 1, 1),
        (10, 40, 2, 5),
    ],
)
def test_grid_tiles_exactly_covers_image_no_gaps_or_overlap(height, width, n_rows, n_cols):
    tiles = grid_tiles(height, width, n_rows, n_cols)
    assert len(tiles) == n_rows * n_cols

    coverage = np.zeros((height, width), dtype=int)
    for tile in tiles:
        coverage[tile.row_slice, tile.col_slice] += 1

    assert np.all(coverage == 1)


def test_grid_tiles_labels_are_unique():
    tiles = grid_tiles(97, 133, 5, 7)
    labels = [t.label for t in tiles]
    assert len(labels) == len(set(labels))


def test_grid_tiles_row_major_order_and_indices():
    tiles = grid_tiles(100, 100, 2, 3)
    expected_indices = [(i, j) for i in range(2) for j in range(3)]
    actual_indices = [(t.row_idx, t.col_idx) for t in tiles]
    assert actual_indices == expected_indices
