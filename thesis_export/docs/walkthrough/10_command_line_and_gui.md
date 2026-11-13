# 10. Command line and GUI

**Files**:
- `src/analyze.py` (126 lines): command line.
- `app.py` (328 lines): GUI.
- `src/crackgraph/grouping.py`, `src/crackgraph/gui/`: the GUI's Compare images board.
- `scripts/batch_stats/`: helpers for the thesis spreadsheets.

Both front ends build an `AnalysisSettings` (page 5) and call `analyze_image` (page 9). Same
choices, same numbers.

---

## `src/analyze.py`

```
python3 -m src.analyze IMAGES_OR_FOLDERS [options]
```

`find_images` (line 31): files as given; folders searched recursively. No selection by name.

### Options (`parse_args`, line 59)

| Option | Meaning |
|---|---|
| `--out-dir` | Output folder. Default `outputs/analysis`. |
| `--um-per-px` | µm per pixel. Default 0.6098. |
| `--regions` | `whole` (default), `centre`, `grid`. |
| `--centre-frac` | Centre size as share of width and height. Default 0.5. |
| `--grid` | Grid size, e.g. `3x3`. |
| `--cells` | Cells to report, e.g. `1,4,7`. Default all. |
| `--measure` | Any of `crack_stats` (default), `tortuosity`, `anisotropy`, `segments`. |
| `--groups` | Crack-stats column groups, comma-separated. Default all. |
| `--runtime` | Add runtime columns. |
| `--figures` | Any of `overlay` (default), `panels`, `map`. |
| `--map-column` | Column for `map`. Default `crack_area_pct`. |

`settings_from_args` (line 90) builds the settings; `main` (line 102) runs each image, writes its
figures, then one `results.xlsx`.

```
# Thesis table: whole-image crack stats for a folder
python3 -m src.analyze ../data/raw/T5 --out-dir outputs/t5

# Left column of a 3x3 grid, with tortuosity, anisotropy and per-region figures
python3 -m src.analyze image.jpg --regions grid --grid 3x3 --cells 1,4,7 \
    --measure crack_stats tortuosity anisotropy --figures overlay panels map
```

---

## `app.py`

```
python3 -m streamlit run app.py
```

Opens at http://localhost:8501; runs locally. `settings_form` (line 34) follows the run order:

1. Calibration: µm per pixel.
2. Region: whole, centre (size slider), or grid (rows, columns, cells to tick).
3. Measurements: crack stats with column groups, tortuosity, anisotropy, per-segment table,
   runtime.
4. Figures: overlay, panels, map (and its column).

It returns `None`, with a hint, if no cell or no measurement is ticked.

`main` (line 304): on **Run analysis**, calls `run_analysis` (line 119), which saves the uploads
to a temporary folder and runs each image. The progress bar moves per engine step (`on_stage`,
line 136). A failing image is reported at the end without stopping the others.

The run's results are kept in `st.session_state`, so they stay on the page while you use the
controls below them. Changing settings has no effect until you click **Run analysis** again.
`show_results` (line 157) shows figures and tables; `download_section` (line 290) offers the
workbook.

### Compare images (`compare_section`, line 185)

Sorts the analysed images into groups, without a hand-written table and whatever your folders
or file names look like.

1. Name what you varied (columns) and, optionally, a second factor (rows), and list their values.
2. Sort the images onto the board: drag them, or click several and then click a cell. Keyboard:
   Enter selects a thumbnail, and Enter on a cell moves the selection there. Images in one cell
   are replicates. Images left in **Unsorted** are left out.
3. **Pre-sort by file name** (optional) places an image only when exactly one column value (and
   one row value) appears as a whole part of its name. `gap150` doesn't match `50`. Anything else
   stays in Unsorted for you to place.

Below the board: the labels table and a replicates plot of any numeric result, for one region at
a time. Each dot is one image. A mean bar is drawn only for groups of 2 or more, and n = 1 is shown
in red. The labels are saved as a `labels` sheet in the downloaded workbook.

Code:
- `src/crackgraph/grouping.py`: pre-sort, labels table, replicates plot. No Streamlit; tested
  in `tests/test_grouping.py`.
- `src/crackgraph/gui/board.py` and `gui/grouping_board/index.html`: the board, a Streamlit
  custom component in one HTML file with no build step and no network access. Python owns the
  assignment and bumps a revision number whenever it changes it (pre-sort, clear, new rows or
  columns). Moves from the browser carry that number, so a stale one is ignored.
- Labels are what you assigned. The tool doesn't check them against the images.

---

## `scripts/batch_stats/`

- `export_crack_stats_batch_bcd.py`: thesis batches B, C, D (19 images): T5 PTFE gap heights;
  humidity series on membrane (75RH_NR212_v2 left out on request); T2/T3/T4 on membrane. Whole
  image, crack stats, runtime, plus a `batch` column. Stops first if any file is missing.
- `add_definitions_sheet.py`: adds a `definitions` sheet (definition, unit, evidence tag per
  column) to a workbook.

---

## Worth knowing

- **What it replaced** (2026-11-13; archived in `archive/thesis_export_old_entry_points_2026-11-13/`):
  - crack-stats export → `--regions whole`
  - `analyze_image.py` (top-left corner) → a corner cell, e.g. `--grid 8x8 --cells 1`
  - spatial overview → `--regions grid --grid 2x2 --figures panels`
- **Tests** (`tests/test_entry_points.py`): the command line end to end, a bad cell refused, the
  GUI starts without errors, and Compare images pre-sorts and labels a seeded run. The board's
  drag and drop runs in the browser, and no automated test covers it.
