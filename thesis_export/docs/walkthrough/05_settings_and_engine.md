# 5. Settings and the engine

**Files**:
- `src/crackgraph/settings.py` (80 lines): every user setting, in one object.
- `src/crackgraph/engine.py` (109 lines): runs pages 1–4 once per image.

The GUI or command line fills an `AnalysisSettings`. The engine runs binarize → skeletonize →
flaking → graph once and hands the result to every measurement, so all measurements describe the
same skeleton.

---

## `settings.py`

### Defaults, lines 22–34

| Line | Name | Meaning |
|---|---|---|
| 24 | `DEFAULT_UM_PER_PX` | 100/164 ≈ 0.6098 µm/px, the thesis microscope (from an external calibration tool). |
| 28 | `SPUR_UM` | Spur cut-off: 15 px × 0.6098 = 9.15 µm (why 15 px: page 2). |
| 29 | `DARK_SPECK_AREA_UM2` | Dark-speck limit: 130 px × 0.6098² = 48.3 µm². |
| 33 | `CRACK_STATS_GROUPS` | area, width, segment_length, connectivity, flaking, pruning. |
| 34 | `MEASUREMENTS` | crack_stats, tortuosity, anisotropy, segments. |

**Why µm.** Both thresholds rest on agglomerate size, a physical length. Stored in µm, they're
converted with your µm per pixel. Defined from the thesis pixel values, so the default run uses
exactly 15 px and 130 px.

### `AnalysisSettings`, line 38

| Field | Default | Meaning |
|---|---|---|
| `um_per_px` | 0.6098 | Converts `_um` columns and the two thresholds. |
| `spur_um`, `dark_speck_area_um2` | 9.15, 48.3 | Physical thresholds. Not in the GUI yet. |
| `curvature_window_px`, `orientation_window_px` | 10 px | Windows for page 8. Not in the GUI yet. |
| `regions` | whole image | Page 6. |
| `measurements` | crack stats | Which measurements run. |
| `crack_stats_groups` | all six | Which crack-stats columns. |
| `include_runtime` | off | Adds time per stage. |

- `__post_init__` (line 51): rejects a calibration ≤ 0 or an unknown name.
- `spur_px` (line 62): cut-off in px, rounded to 6 decimals so 15 stays 15.
- `dark_speck_area_px` (line 67): limit in whole pixels.

### `settings_record(settings)`, line 71

Every setting plus the derived pixel thresholds, written to the workbook's `settings` sheet.

---

## `engine.py`

### `EngineResult`, line 30

Image size, each step's result, `omitted` (flake-touching segments) and step times. Helpers:

| Helper | Line | What it does |
|---|---|---|
| `kept_paths` | 41 | Segments not touching a flake. Measurements use only these. |
| `path_pixels(p)` | 45 | (row, col) pixels of segment `p`, cached. |
| `path_midpoint(p)` | 52 | Middle pixel of segment `p`, which decides its region (page 6). |

### `run_engine(gray, settings, on_stage)`, line 60

| Lines | Step |
|---|---|
| 68–71 | Binarize (page 1). |
| 73–81 | Skeletonize once, with thresholds converted from your calibration (page 2). |
| 83–88 | Find flaked patches from the width map (page 3). |
| 90–92 | Build the graph (page 4). |
| 94–99 | List segments with a pixel in a flaked patch. |

`on_stage`, if given, is called after each step (`ENGINE_STAGES`, line 26); the GUI uses it for
its progress bar.

---

## Worth knowing

- One engine run per image, whatever the regions: about 20–45 s for a thesis image.
- **Tests** (`tests/test_unified_analysis.py`): default calibration gives exactly 15 px and
  130 px; doubling the magnification doubles the cut-off.
