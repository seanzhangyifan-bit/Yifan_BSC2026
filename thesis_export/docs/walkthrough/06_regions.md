# 6. Regions

**File**: `src/crackgraph/regions.py` (139 lines)

**What it does.** It turns your choice (whole image, centre, or chosen cells of a grid) into a
list of rectangles. Each rectangle gets its own row of numbers.

**The key idea.** The engine runs once on the whole image (page 5). A region doesn't re-run
anything: it only decides which part of that one result a row describes. So every grid cell is
measured with the same threshold and the same flaking reference width as the whole image, and
the cells' crack areas add up to the whole image's.

The other way, re-running on each crop, would give every cell its own Otsu threshold and
flaking reference. Cells would then be measured differently from each other, and a 10×10 grid
would take 100 runs.

---

## `Region`, line 22

One rectangle: a label (`"whole"`, `"centre"` or `"cell 5 (r2c2)"`) and its first and last
row and column. The stop values are exclusive, as in Python slices.

| Helper | Line | What it does |
|---|---|---|
| `row_slice`, `col_slice` | 30, 34 | Ready-made slices, so `mask[region.row_slice, region.col_slice]` cuts the region out of any image-sized array. |
| `area_px` | 38 | The region's area in pixels. |
| `is_whole_image(shape)` | 41 | True if the region covers the whole image. Connectivity is only measured then (page 7). |
| `contains_point(row, col)` | 44 | Whether one point lies inside. |
| `contains(rows, cols)` | 47 | The same for many points at once: returns one True/False per point. |

## `RegionSpec`, line 56

Your choice, independent of any image's size:

| Field | Meaning |
|---|---|
| `mode` | `"whole"`, `"centre"` or `"grid"`. |
| `centre_frac` | For `"centre"`: the share of the width and height. 0.5 = the middle half along each side, so a quarter of the image area. |
| `n_rows`, `n_cols` | For `"grid"`: the grid size. |
| `cells` | For `"grid"`: which cells to report, numbered 1 to rows × columns, row by row from the top left. `None` = every cell. |

- **`__post_init__`, line 72**: stops with a clear message on an impossible choice, for
  example cell 9 in a 2×2 grid.
- **`describe()`, line 87**: a one-line description, such as "3x3 grid, cells 1,4,7", for the
  settings sheet and the command line.
- **`regions(height, width)`, line 95**: the actual rectangles for one image. The centre
  rectangle is rounded to whole pixels and centred.

## `grid_cells(...)`, line 107

Cell boundaries are at `round(i × height / n_rows)`, so when the image doesn't divide evenly,
the spare pixels are spread across cells rather than all landing in the last row or column.
Every pixel is in exactly one cell, edge to edge.

## `corner_crop(...)`, line 130

A square near the top-left corner, inset by 2% of the image width, sized 1/8 of the width. It's
not one of the region choices. Two validation sweeps (`pipeline_stage_figures.py`,
`segmentation_sensitivity_sweep.py`) use it so their results stay comparable with earlier runs.
It replaces the old `region.py`.

---

## How a region cuts the measurements

Two rules, depending on what's being counted. Page 7 applies them.

| What | Rule | Why |
|---|---|---|
| Pixels: crack area, flaked area, per-pixel width, total crack length | Only the pixels inside the region count. | Cells add up to the whole image. |
| Segments: segment length and count, pruned branches, tortuosity | Each segment goes **whole** to the region holding its middle pixel. | A segment cut by a cell border isn't counted as two short ones, so the segment lengths stay comparable. |
| Direction samples (anisotropy) | Each sample goes to the region it lies in. | Samples are already local. |
| Connectivity | Whole image only. | Cutting at a border splits the network, so a region's connectivity would mostly reflect its size. |

**Tests**: `tests/test_unified_analysis.py` checks that grid cells cover every pixel exactly
once, that a 3×3 grid's crack area adds up to the whole image, and that an impossible cell
number is refused. `tests/test_crack_stats_measure.py` checks that a segment crossing a cell
border is counted in one cell only.
