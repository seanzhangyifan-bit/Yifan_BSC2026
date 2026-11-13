# 8. The per-image command

**File**: `src/analyze_image.py` (430 lines)

**What it does.** It's the one command that analyses one image in detail:

```
python3 -m src.analyze_image path/to/image.jpg
```

It prints a long report with an evidence label on every number, and writes:
- an overlay picture
- a per-segment CSV
- optionally, a spreadsheet row

It's mostly *wiring*: almost every calculation happens in the modules from pages 1–7.

**By default it analyses only a corner crop**: a square 1/8 of the image width, inset 2% from
the top-left corner (`region.py`). That's about **1.5% of the image area**. The report states
the region and its area share at the top, so corner numbers aren't mistaken for whole-image
numbers like the batch crack stats. Pass `--full-image` to analyse the whole image.

---

## Settings, lines 44–50

`EXPECTED_WIDTH_PX_RANGE` / `EXPECTED_HEIGHT_PX_RANGE`: the size of a normal 5 mm mosaic capture.
A different size prints a warning, because it's probably the wrong kind of image.

## `parse_args()`, line 53: the options

Every tunable setting from earlier pages can be overridden from the command line, for example
`--spur-px`, `--curvature-window-px` or `--width-trim-inner-px`, with defaults taken from the
modules. Notable switches:

| Option | Effect |
|---|---|
| `--full-image` | Analyse the whole image, not the corner crop. |
| `--no-host-stub-pruning` | Keep the short dead ends that the skeleton step would otherwise remove (page 2). |
| `--skip-curvature`, `--skip-anisotropy` | Skip those measurements. |
| `--xlsx-out FILE` | Append a summary row to a workbook. Refuses to combine with any `--skip-*`. |

## `main()`, line 102

In order:

### 1. Load and crop, lines 103–141
Load the image, warn if it's an unusual size, and cut out the corner crop unless `--full-image`.

### 2. Run the pipeline, lines 143–195
| Lines | Step | Page |
|---|---|---|
| 143 | Binarize | 1 |
| 149–173 | Skeleton → flaking → remove edges touching a flaked region, rebuild the graph | 2, 3, 4 |
| 174–187 | Curvature and anisotropy (unless skipped) | 7 |
| 188–195 | Per-segment metrics (always) | 6 |

### 3. Write files, lines 199–209
Outputs go to `outputs/<image's folder name>/`. Files are named `<image>_<corner|full>_...`:
- `..._edge_metrics.csv`: per-segment table.
- `..._overlay.png`: skeleton, endpoints (orange) and junctions (red).

### 4. Print the report, lines 211–409
One section per stage, each number tagged `[measured]`, `[interpreted]` or `[PLACEHOLDER]`:
- every option value used, plus library versions, so the run can be reproduced exactly
- binarize threshold and foreground fraction
- flaking candidates
- pruning counts
- node counts
- curvature and tortuosity
- anisotropy with a text histogram
- the four area estimates and widths per segment

The app's progress bar (page 10) watches for these section headers to know how far along the run
is.

### 5. Optional spreadsheet row, lines 411–426
With `--xlsx-out`, it appends a summary row through `xlsx_report.append_chunk_to_workbook`
(page 9).

## Worth knowing

- **Segments touching a flaked region** are removed from the skeleton before any analysis, so
  curvature, anisotropy and the per-segment metrics never see them. The report says how many.
- **Tests**: `tests/test_entry_points.py` runs `main()` on a small synthetic flaked grid. It checks
  the files appear and the report has its sections, not the numbers. The pieces it calls are
  tested individually.
