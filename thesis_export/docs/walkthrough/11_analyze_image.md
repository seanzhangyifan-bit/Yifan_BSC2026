# 11. The per-image command

**File**: `src/analyze_image.py` (753 lines)

**What it does.** It's the one command that runs the **whole** ordering analysis on one image:

```
python3 -m src.analyze_image path/to/image.jpg
```

It prints a long report with an evidence label on every number, and writes:
- overlay pictures
- a precedence picture
- a per-segment CSV
- optionally, a spreadsheet row

It's mostly *wiring*: almost every calculation happens in the modules from pages 1–10.

**By default it analyses only a corner crop**: a square 1/8 of the image width, inset 2% from
the top-left corner (`region.py`). That's about **1.5% of the image area**. The report states
the region and its area share at the top and again next to the junction counts, so corner
counts aren't mistaken for whole-image numbers. The ordering analysis was validated at that size; full-image
runs (`--full-image`) are allowed but not validated yet.

---

## Settings, lines 58–64

`EXPECTED_WIDTH_PX_RANGE` / `EXPECTED_HEIGHT_PX_RANGE`: the size of a normal 5 mm mosaic capture.
A different size prints a warning, because it's probably the wrong kind of image.

## `parse_args()`, line 67: the options

Every tunable setting from earlier pages can be overridden from the command line, for example
`--spur-px`, `--annulus-outer-px` or `--y-angle-tol-deg`, with defaults taken from the modules.
Notable switches:

| Option | Effect |
|---|---|
| `--full-image` | Analyse the whole image, not the corner crop. |
| `--show-fit-detail` | Also draw a diagnostic overlay showing each fitted arm curve. |
| `--hide-corner-check` | Hide corner markers from the overlay; the check still runs. |
| `--skip-curvature`, `--skip-anisotropy` | Skip those measurements. |
| `--skip-junctions` | Skip junctions, which also skips the corner check and precedence (both need it). |
| `--skip-corner-cross-check`, `--skip-precedence` | Skip just those. |
| `--xlsx-out FILE` | Append a summary row to a workbook. Refuses to combine with any `--skip-*`. |

## `main()`, line 171

It's about 550 lines. Splitting it into "run" and "print" parts is review item R1. In order:

### 1. Load and crop, lines 172–210
Load the image, warn if it's an unusual size, and cut out the corner crop unless `--full-image`.

### 2. Run the pipeline, lines 212–314
| Lines | Step | Page |
|---|---|---|
| 212 | Binarize | 1 |
| 217–242 | Scout skeleton → flaking → second skeleton if flakes were found | 2, 3 |
| 243 | Graph | 4 |
| 245–257 | Curvature and anisotropy (unless skipped) | 10 |
| 265–273 | Per-segment metrics (always) | 6 |
| 275–285 | Junction classification, passing the width map so the ring widens on thick cracks | 7 |
| 288–301 | Corner cross-check (needs junctions) | 8 |
| 305–314 | Precedence graph (needs junctions; works with or without the corner check) | 9 |

### 3. Write files, lines 316–361
Outputs go to `outputs/<image's folder name>/`. Files are named `<image>_<corner|full>_...`:
- `..._edge_metrics.csv`: per-segment table.
- `..._precedence.png`: segments coloured by generation.
- `..._overlay.png`: skeleton, endpoints and T/Y markers.
- `..._overlay_detail.png`: with fitted curves, if `--show-fit-detail`.

### 4. Print the report, lines 363–730
One section per stage, each number tagged `[measured]`, `[interpreted]` or `[PLACEHOLDER]`:
- every option value used, plus library versions, so the run can be reproduced exactly
- binarize threshold and foreground fraction
- flaking candidates
- pruning counts
- node counts
- curvature and tortuosity
- anisotropy with a text histogram
- the four area estimates and widths per segment
- every junction's label and gaps
- corner-check agreement
- precedence arrows, conflicts and cycles

The app's progress bar (page 13) watches for these section headers to know how far along the run
is.

### 5. Optional spreadsheet row, lines 732–749
With `--xlsx-out`, it appends a summary row through `xlsx_report.append_chunk_to_workbook`
(page 12).

## Worth knowing

- **Segments next to a flaking cut** are left out of the length/width totals, as in the batch
  exporter. The report says how many and how long.
- **Tests**: `tests/test_entry_points.py` runs `main()` on a small synthetic flaked grid. It checks
  the files appear and the report has its sections, not the numbers. The pieces it calls are
  tested individually.
