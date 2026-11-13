# 10. Command line and GUI

**Files**:
- `src/analyze.py` (126 lines): the command line.
- `app.py` (177 lines): the browser GUI.
- `scripts/batch_stats/`: two helpers for the thesis spreadsheets.

**What they do.** Both front ends build an `AnalysisSettings` (page 5) from your choices and call
`analyze_image` (page 9) on each image. They offer the same choices and produce the same
numbers; pick whichever is easier.

---

## `src/analyze.py`: the command line

```
python3 -m src.analyze IMAGES_OR_FOLDERS [options]
```

`find_images` (line 31) takes image files and folders; a folder is searched in every subfolder.
It doesn't select by file name: which images get analysed is up to you.

### Options, `parse_args`, line 59

| Group | Option | Meaning |
|---|---|---|
| | `--out-dir` | Where results go. Default `outputs/analysis`. |
| calibration | `--um-per-px` | µm per pixel. Default 0.6098, the thesis microscope. |
| regions | `--regions` | `whole` (default), `centre` or `grid`. |
| | `--centre-frac` | For `centre`: share of width and height. Default 0.5. |
| | `--grid` | For `grid`: rows×columns, for example `3x3`. |
| | `--cells` | For `grid`: which cells, for example `1,4,7`. Default: all. |
| what to measure | `--measure` | Any of `crack_stats` (default), `tortuosity`, `anisotropy`, `segments`. |
| | `--groups` | Crack-stats column groups, comma-separated. Default: all six. |
| | `--runtime` | Add runtime columns. |
| | `--scale-bars-checked` | Record that you checked every image for a burned-in scale bar. |
| figures | `--figures` | Any of `overlay` (default), `panels`, `map`. |
| | `--map-column` | The column the `map` figure draws. Default `crack_area_pct`. |

`settings_from_args` (line 90) turns these into an `AnalysisSettings`. `main` (line 102) runs
each image, writes its figures, then writes one `results.xlsx` for the whole run.

### Examples

```
# The thesis table: crack stats on the whole image, every image in a folder
python3 -m src.analyze ../data/raw/T5 --out-dir outputs/t5

# The left column of a 3x3 grid, with tortuosity, anisotropy and the per-region figures
python3 -m src.analyze image.jpg --regions grid --grid 3x3 --cells 1,4,7 \
    --measure crack_stats tortuosity anisotropy --figures overlay panels map
```

---

## `app.py`: the GUI

```
python3 -m streamlit run app.py
```

It opens at http://localhost:8501 and runs on your computer only; nothing is uploaded. If
`streamlit run app.py` says "command not found", that's a PATH issue: the `python3 -m` form
above always works.

The page follows the order the analysis runs in. `settings_form` (line 34) draws:

1. **Calibration**: µm per pixel.
2. **Which part of the image**: whole image, centre (with a slider for its size), or grid (rows,
   columns, and a list of cells to tick).
3. **What to measure**: crack stats with a choice of column groups, tortuosity, anisotropy, the
   per-segment table, runtime columns.
4. **Figures**: overlay, panels, map (and the map's column).

It returns `None`, and the page shows a hint, if the choices can't make a run: no cell or no
measurement ticked.

`main` (line 109) waits for **Run analysis**, saves the uploaded files to a temporary folder,
and runs `analyze_image` on each. The progress bar moves after every step the engine reports
(`on_stage`, line 139). One image failing doesn't stop the others: its error is shown at the
end. The figures appear per image, then every table, then a button to download the workbook.

---

## `scripts/batch_stats/`

- **`export_crack_stats_batch_bcd.py`**: the thesis batches B, C and D (19 images): T5 PTFE gap
  heights, the humidity series on membrane (75RH_NR212_v2 left out at your request), and
  T2/T3/T4 on membrane. Whole image, crack stats, runtime columns, plus a `batch` column. If any
  listed file is missing under `--data-dir`, it lists them all and stops before doing any work.
- **`add_definitions_sheet.py`**: adds a `definitions` sheet to a finished workbook: one row per
  stats column, with a one-line definition, unit and evidence tag.

---

## Worth knowing

- **What replaced what.** Until 2026-11-13 there were three separate commands: the crack-stats
  export (whole image), `analyze_image.py` (top-left corner by default, with tortuosity and
  anisotropy), and the spatial overview (four quadrants). They're archived in the repository's
  `archive/thesis_export_old_entry_points_2026-11-13/`. Their jobs are now settings of the one
  command: `--regions whole`; a corner cell, such as `--grid 8x8 --cells 1`; and
  `--regions grid --grid 2x2 --figures panels`.
- **Tests**: `tests/test_entry_points.py` runs the command line end to end, checks that a cell
  outside the grid is refused, and loads the GUI to check it starts without errors.
