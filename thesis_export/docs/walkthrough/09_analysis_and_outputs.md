# 9. One run, start to finish

**Files**:
- `src/crackgraph/analysis.py` (137 lines): image + settings → one row per region.
- `src/crackgraph/measures/segments.py` (50 lines): optional per-segment table.
- `src/crackgraph/export.py` (65 lines): workbook and figures.
- `src/crackgraph/figures.py` (129 lines), drawing with `overlay.py` and `summary_plots.py`.

`analyze_image` is the one function the GUI and command line both call:

```
image ──► engine (once) ──► regions ──► measurements ──► one row per region
          page 5            page 6      pages 7–8         + figures, workbook
```

---

## `analysis.py`

- `analysis_stages(settings)` (line 32): the progress steps a run will report, so the GUI can size
  its progress bar.
- `ImageAnalysis` (line 45): the run's result.

| Field | Meaning |
|---|---|
| `rows` | One dict per region: the spreadsheet numbers. |
| `image_connectivity` | Whole-image connectivity, when asked for and the regions aren't the whole image. |
| `segments` | The per-segment table, if asked for. |
| `anisotropy`, `curvature` | Per-region details for the figures. |

### `analyze_image(image_path, settings, ...)`, line 62

| Lines | Step |
|---|---|
| 72–76 | Load, run the engine, build the regions. |
| 78–89 | Scan curvature and directions once, if asked for. |
| 93–104 | Start each region's row: file, folder, region, its pixel range, its area share. |
| 105–116 | Add each measurement's columns. |
| 118–128 | Whole-image connectivity, when the regions don't include the whole image. |
| 133–136 | Runtime columns, if asked for (per image, repeated on each region row). |

---

## `measures/segments.py`

One row per kept segment, under the region holding its middle pixel.

| Column | Meaning |
|---|---|
| `segment` | skan's `path_index`. |
| `mid_row_px`, `mid_col_px` | Middle pixel, to find it on the overlay. |
| `length_px`, `length_um` | Full length. |
| `median_width_px`, `median_width_um` | Median of 2 × half-width along the segment. |
| `area_px2`, `area_um2` | Width integrated along the centre line (`ribbon_area_px2`, line 14). `[interpreted]`: runs high through wide junctions. |

---

## `export.py`

| Function | Line | What it does |
|---|---|---|
| `results_tables` | 22 | `regions`, plus `image_connectivity` and `segments` when non-empty. |
| `write_workbook` | 33 | One `.xlsx` with those sheets plus `settings`. |
| `write_figures` | 44 | Chosen figures as PNGs under `<out-dir>/<image folder>/`; skips empty ones. |

## `figures.py`

| Figure | Function, line | Shows |
|---|---|---|
| `overlay` | `render_overlay_with_regions`, 32 | Skeleton on the micrograph: kept segments green, flake-touching magenta, flaked patches red, regions outlined and numbered (except whole image). |
| `panels` | `render_region_panels`, 64 | Rose plot and tortuosity histogram per region, placed like the grid. Shared histogram bins (line 42). Skipped above 36 regions (line 29). |
| `map` | `render_region_map`, 95 | One column as a colour map over the regions, values written in each cell. Needs more than one region. |

---

## Tests

- `tests/test_entry_points.py`: a grid run with every measurement and figure; checks every sheet
  and file.
- `tests/test_summary_plots.py`: rose and histogram drawing, including empty data.
