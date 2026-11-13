# 6. Regions

**File**: `src/crackgraph/regions.py` (139 lines)

Turns your choice (whole image, centre, grid cells) into rectangles; each gets a row.

**Key idea.** The engine runs once on the whole image (page 5). A region only selects part of that
result. All regions share one threshold and one flaking reference, and cells add up to the whole.
Re-running per crop would give each cell its own threshold, and a 10×10 grid would take 100 runs.

---

## `Region`, line 22

A label (`whole`, `centre`, `cell 5 (r2c2)`) and its row and column range (stop exclusive).

| Helper | Line | What it does |
|---|---|---|
| `row_slice`, `col_slice` | 30, 34 | Slices for cutting the region out of any image-sized array. |
| `area_px` | 38 | Area in pixels. |
| `is_whole_image(shape)` | 41 | True if it covers the image. Connectivity runs only then (page 7). |
| `contains_point(row, col)` | 44 | Is one point inside? |
| `contains(rows, cols)` | 47 | Same, for many points. |

## `RegionSpec`, line 56

Your choice, independent of image size:

| Field | Meaning |
|---|---|
| `mode` | `whole`, `centre` or `grid`. |
| `centre_frac` | For `centre`: share of width **and** height. 0.5 → middle half each way = 25% of the area. |
| `n_rows`, `n_cols` | For `grid`: grid size. |
| `cells` | For `grid`: cells to report, numbered row by row from the top left. `None` = all. |

- `__post_init__` (line 72): rejects impossible choices, e.g. cell 9 in a 2×2 grid.
- `describe()` (line 87): one-line description, e.g. "3x3 grid, cells 1,4,7".
- `regions(height, width)` (line 95): the rectangles for one image.

## `grid_cells(...)`, line 107

Boundaries at `round(i × height / n_rows)`, so spare pixels spread across cells. Every pixel is in
exactly one cell.

## `corner_crop(...)`, line 130

A square near the top-left corner (1/8 of the width, inset 2%). Not a user choice: two validation
sweeps use it to stay comparable with earlier runs.

---

## How a region cuts the measurements

| What | Rule | Why |
|---|---|---|
| Pixels: crack area, flaked area, width, total length | Pixels inside the region. | Cells add up to the whole. |
| Segments: length, count, pruned branches, tortuosity | Whole segment, placed by its middle pixel. | No segment counted twice or cut short. |
| Direction samples (rose plot) | By the sample's own position. | Samples are already local. |
| Connectivity | Whole image only. | Cutting at a border splits the network. |

**Tests**: `tests/test_unified_analysis.py` (cells cover every pixel once; 3×3 crack area adds up;
bad cell refused). `tests/test_crack_stats_measure.py` (a border-crossing segment counts once).
