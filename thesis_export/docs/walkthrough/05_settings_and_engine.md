# 5. Settings and the engine

**Files**:
- `src/crackgraph/settings.py` (80 lines): every setting you can change, in one object.
- `src/crackgraph/engine.py` (109 lines): runs pages 1–4 once on a whole image.

**What they do.** Every run starts with an `AnalysisSettings` object, filled in by the GUI or by
the command line. The engine takes an image and those settings, runs binarize → skeletonize →
flaking → graph once, and hands one result to every measurement. Crack stats, tortuosity and
anisotropy therefore always describe the same skeleton.

---

## `settings.py`

### Defaults, lines 22–34

| Line | Name | Meaning |
|---|---|---|
| 24 | `DEFAULT_UM_PER_PX` | 100/164 ≈ 0.6098 µm per pixel: the microscope calibration for the thesis images, taken from an external calibration tool. |
| 28 | `SPUR_UM` | The spur cut-off in µm: 15 px × 0.6098 = 9.15 µm. Page 2 explains why 15 px. |
| 29 | `DARK_SPECK_AREA_UM2` | The dark-speck limit in µm²: 130 px × 0.6098² = 48.3 µm². |
| 33 | `CRACK_STATS_GROUPS` | The crack-stats column groups you can choose: area, width, segment length, connectivity, flaking, pruning. |
| 34 | `MEASUREMENTS` | What can run on each region: crack stats, tortuosity, anisotropy, and the per-segment table. |

**Why the two thresholds are in µm.** Both are justified by a physical size: the largest
agglomerates (page 2). An agglomerate is the same size in µm whatever the magnification, so the
thresholds are stored in µm and converted to pixels with your µm per pixel. They're defined
*from* their pixel values at the thesis calibration, so the default run uses exactly 15 px and
130 px, and the thesis numbers don't change.

### `AnalysisSettings`, line 38

A plain container (a `@dataclass`) with one field per setting:

| Field | Default | Meaning |
|---|---|---|
| `um_per_px` | 0.6098 | Calibration. Converts every `_um` column and the two thresholds. |
| `spur_um`, `dark_speck_area_um2` | 9.15, 48.3 | The two physical thresholds. Not in the GUI yet. |
| `curvature_window_px`, `orientation_window_px` | 10 px each | Window sizes for page 8. Not in the GUI yet. |
| `regions` | whole image | Which part of the image to report on (page 6). |
| `measurements` | crack stats only | Which measurements run. |
| `crack_stats_groups` | all six | Which crack-stats columns to include. |
| `include_runtime` | off | Adds how long each stage took. |

- **`__post_init__`, line 51**: runs when the object is made, and stops with a clear message if a
  value can't work: a calibration of 0 or less, or a measurement name that doesn't exist.
- **`spur_px`, line 62**: the spur cut-off in pixels. It's rounded to 6 decimals, so float error
  can't turn 15 into 14.999999999999998.
- **`dark_speck_area_px`, line 67**: the dark-speck limit in whole pixels.

### `settings_record(settings)`, line 71

Every setting as a flat `{name: value}` list, plus the two derived pixel thresholds. It's
written to the `settings` sheet of every results workbook (page 9), so you can tell how any set
of numbers was made.

---

## `engine.py`

### `EngineResult`, line 30

What the engine returns: the image size, each step's result (pages 1–4), `omitted` (the
segments touching a flaked patch) and how long each step took. Three helpers that the
measurements use:

| Helper | Line | What it does |
|---|---|---|
| `kept_paths` | 41 | Every segment *not* touching a flaked patch. Measurements only use these. |
| `path_pixels(p)` | 45 | The (row, column) pixels along segment `p`. Kept in memory after the first call, because several measurements ask for the same segment. |
| `path_midpoint(p)` | 52 | The middle pixel of segment `p`. A segment belongs to the region that holds its middle pixel (page 6). |

### `run_engine(gray, settings, on_stage)`, line 60

| Lines | Step |
|---|---|
| 68–71 | Binarize (page 1). |
| 73–81 | Skeletonize (page 2), once, with the spur cut-off and dark-speck limit converted from your calibration. |
| 83–88 | Find flaked patches from that skeleton's width map (page 3). |
| 90–92 | Build the graph (page 4). |
| 94–99 | List every segment with a pixel inside a flaked patch. These are left out of every measurement. |

`on_stage` is an optional callback: after each step the engine calls it with the step's name
(`ENGINE_STAGES`, line 26). The GUI uses it to move its progress bar.

---

## Worth knowing

- **One engine run per image, whatever the regions.** A 10×10 grid costs the same as the whole
  image: about 20–45 s for a thesis image.
- **The same steps, in the same order, as the old crack-stats exporter.** The old exporter was
  archived on 2026-11-13. `tests/test_unified_analysis.py` checks that the whole-image numbers
  still match its frozen output exactly.
- **Tests**: `tests/test_unified_analysis.py` also checks that the default calibration gives
  exactly 15 px and 130 px, and that doubling the magnification doubles the spur cut-off.
