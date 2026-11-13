# 9. One run, start to finish

**Files**:
- `src/crackgraph/analysis.py` (137 lines): one image and its settings → one row per region.
- `src/crackgraph/measures/segments.py` (50 lines): the optional per-segment table.
- `src/crackgraph/export.py` (65 lines): writes the results workbook and the figures.
- `src/crackgraph/figures.py` (129 lines), plus the older `overlay.py` and `summary_plots.py`
  it draws with: the pictures.

**What they do.** `analyze_image` is the single function the GUI and the command line (page 10)
both call. It ties pages 5–8 together:

```
image ──► engine (once) ──► regions ──► measurements ──► one row per region
          page 5            page 6      pages 7–8         + figures and workbook
```

---

## `analysis.py`

### `analysis_stages(settings)`, line 32

The progress-step names a run with these settings will report, in order, so the GUI can size its
progress bar before starting.

### `ImageAnalysis`, line 45

What one run returns: the image, the settings, the engine result, the regions, and:

| Field | Meaning |
|---|---|
| `rows` | One dictionary per region: the numbers that go in the spreadsheet. |
| `image_connectivity` | Whole-image connectivity, only when you asked for connectivity and the regions aren't the whole image (page 7). |
| `segments` | The per-segment table, only if you asked for it. |
| `anisotropy`, `curvature` | Each region's detailed results, kept for the figures. |

### `analyze_image(image_path, settings, ...)`, line 62

| Lines | Step |
|---|---|
| 72–76 | Load the image, run the engine once (page 5), and turn your region choice into rectangles (page 6). |
| 78–89 | If you asked for them, scan curvature and direction samples once over the whole image (page 8). |
| 93–104 | For each region, start a row with what identifies it: file, folder, region label, its rows and columns in pixels, and its share of the image area. |
| 105–116 | Add each requested measurement's columns to the row. |
| 118–128 | Whole-image connectivity, when the regions don't already include the whole image. |
| 133–136 | Runtime columns, if asked for. They're per image, so every region row of one image repeats them. |

`scale_bar_check` is written into every row as given: "visually confirmed" only if whoever
started the run says every image was checked for a burned-in scale bar.

---

## `measures/segments.py`: the per-segment table

One row per kept segment, listed under the region holding its middle pixel:

| Column | Meaning |
|---|---|
| `segment` | skan's `path_index`. |
| `mid_row_px`, `mid_col_px` | The segment's middle pixel, to find it on the overlay. |
| `length_px`, `length_um` | Full length, not cut at the region border. |
| `median_width_px`, `median_width_um` | Median of 2 × half-width along the segment. |
| `area_px2`, `area_um2` | Width integrated along the centre line (`ribbon_area_px2`, line 14). `[interpreted]`: runs a little high where a segment passes through a wide junction. |

It replaces the old per-segment output, which compared four area methods. That comparison is
archived with `edge_metrics.py`.

---

## `export.py`

| Function | Line | What it does |
|---|---|---|
| `results_tables(analyses)` | 22 | The run's tables: `regions`, plus `image_connectivity` and `segments` when they have content. |
| `write_workbook(...)` | 33 | One `.xlsx` with those tables as sheets, plus a `settings` sheet listing every setting used. |
| `write_figures(...)` | 44 | The figures you chose, as PNGs under `<out-dir>/<image's folder>/`. Returns the files it wrote: a figure with nothing to show is skipped. |

## `figures.py`

| Figure | Function, line | What it shows |
|---|---|---|
| `overlay` | `render_overlay_with_regions`, 32 | The skeleton on the micrograph: kept segments green, segments touching a flake magenta, flaked patches red. Regions are outlined in yellow and numbered, unless the region is the whole image. Drawn by `overlay.py`'s `render_crack_stats_overlay`. |
| `panels` | `render_region_panels`, 64 | One orientation rose and tortuosity histogram per region. For a grid, each panel sits where its cell sits in the image, so spatial differences read straight off the figure. All histograms share one set of bins (`_shared_tortuosity_bins`, line 42). Skipped above 36 regions (`MAX_PANEL_REGIONS`, line 29), where the panels get too small to read. |
| `map` | `render_region_map`, 95 | One column of the region table as a colour map over the regions, on a faded copy of the micrograph, with each value written in its cell. Only drawn for more than one region. |

The rose plots and histograms themselves come from `summary_plots.py`, which the validation
gallery also uses (page 11).

---

## Worth knowing

- **The workbook always records its settings.** A results file on its own is enough to know how
  its numbers were made.
- **Tests**: `tests/test_entry_points.py` runs a grid with every measurement and figure, then
  checks every sheet and figure file exists. `tests/test_summary_plots.py` checks the rose and
  histogram drawing, including empty data.
