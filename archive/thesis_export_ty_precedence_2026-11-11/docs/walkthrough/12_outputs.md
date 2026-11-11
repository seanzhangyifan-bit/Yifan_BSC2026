# 12. Outputs and reports

These files turn results into pictures, spreadsheets, saved caches and HTML pages. None of them
measure anything. Skim this page; come back when you need to change an output.

| File | Lines | Produces |
|---|---|---|
| `overlay.py` | 573 | Results drawn on top of the micrograph |
| `xlsx_report.py` | 345 | One spreadsheet row per `analyze_image` run |
| `cache_io.py` | 161 | Saved intermediate arrays, to redraw or re-check without re-running |
| `summary_plots.py` | 244 | Rose diagrams, histograms, the 2×2 overview figure |
| `html_report.py` | 218 | One HTML page collecting every overview figure |
| `pipeline_figures.py` | 116 | Step-by-step panels for the walkthrough figures |
| `region.py`, `tiling.py` | 44, 54 | The corner crop, and the 2×2 grid split |
| `scripts/spatial_overview/` | 165 | The commands that make the overview figure and HTML report |

---

## `overlay.py`

**One rule throughout.** Big images are shrunk for display, but **only the photo** is resampled.
Skeleton and marker coordinates are multiplied by the same scale factor instead. Resampling a
1-pixel line would blur or break it.

### `render_overlay(...)`, line 105: the main analysis overlay
- Green skeleton, orange loose ends.
- Junctions by label: blue triangle = T, green plus = Y, orange × = ambiguous, grey × =
  unmeasurable, red dot = crossing.
- Gold diamonds for corners found by the cross-check. Corners where it **disagrees** get a red
  edge and a red ring around the junction, since disagreement is a headline signal.
- **Detail mode** (`detail=True`) adds:
  - the angle-gap text per junction
  - the **fitted arm curve**, cyan, drawn *only* over the pixels it was fitted to, so what's drawn
    is what was measured
  - a short tick for the derived direction
  - a dashed grey stretch inside the junction blob, marking "not evidence"
- The legend goes *below* the image, so it never covers junctions.

### `render_crack_stats_overlay(...)`, line 346: the batch-export overlay
- Red tint over flaking-excluded areas.
- Magenta for segments dropped from length/width stats.
- Optional labelled grid squares ("E4") so you can point at a spot when talking about it.

### `render_precedence_overlay(...)`, line 471
- Each segment is coloured by its generation: dark = older, light = younger, grey = no
  generation.
- Each line is drawn at the crack's own measured width, so it covers the crack.

## `xlsx_report.py`

`append_chunk_to_workbook(...)` (line 219) adds one row per `analyze_image --xlsx-out` run:
- one sheet per image
- about 55 columns, from the run settings to junction counts and corner-check agreement
- thumbnails of the rose, histogram and overlay embedded in the row

The small helpers at lines 122–158 compute summary numbers. `analyze_image.py` uses the same
helpers, so the printed report and the spreadsheet can't disagree:
- `tortuosity_stats`, `curvature_stats`
- `corner_agreement_counts`
- `anisotropy_classification`: the "grid-like" (≥ 0.5) / "mud-crack-like" (< 0.15) labels.

The rest handles Excel's sheet-name rules (31 characters, no `[]:*?/\`).

## `cache_io.py`

- **`save_analysis_cache(...)`** (line 83) writes six files per image into `cache_dir/<image>/`:
  - the stats row (`stats.json`)
  - the crack mask minus flakes (`mask_corrected`), final skeleton and excluded-flake mask, as
    compressed arrays
  - the flake candidates
  - every pruned branch with its reason and pixel path
- **`load_analysis_cache(...)`** (line 130) reads them back.

The width map isn't saved, because it's big and quick to recompute. Recompute it from the whole
cleaned mask, flaked regions included, not from `mask_corrected`: that's the map the stats used.

## `summary_plots.py`

- **`render_orientation_rose`** (line 86): the anisotropy histogram as a polar bar chart.
  Each bar is drawn twice, at θ and θ + 180°, because 10° and 190° are the same crack direction.
- **`render_curvature_histogram`** (line 162): tortuosity and mean curvature side by side.
- **`render_overview_figure`** (line 198): **exactly 2×2**:
  - the whole micrograph in the centre
  - each quadrant's rose and tortuosity histogram in the matching corner
  - the whole image's own results along the bottom
  - one shared histogram scale, so panels compare fairly

## `html_report.py`

A small list of entries, `report_data.json`, is the source of truth. `report.html` is
**rewritten** from it in full every time:
- **`update_master_report`** (line 148) adds or replaces one image's entry.
- **`attach_full_analysis_images`** (line 183) adds full-image overlay links to an existing entry.

Entries are grouped by coating (the image's folder name).

## `pipeline_figures.py`

Drawing helpers shared by the stage-by-stage figure scripts in `scripts/validation/`: raw,
binarized, skeleton, and final graph with kept vs omitted segments and nodes. The skeleton is
thickened **for display only**, so it stays visible when shrunk.

## `region.py` and `tiling.py`

- **`default_corner_crop(height, width, corner_frac=0.125, edge_margin_frac=0.02)`** (region.py
  line 20): the analysis window, a square 1/8 of the image width, inset 2% of the width from the
  top-left corner. Both sizes come from the *width*, so the recipe works on slightly different
  image sizes.
- **`grid_tiles(height, width, n_rows, n_cols)`** (tiling.py line 30): split the image into
  non-overlapping tiles covering every pixel, with leftover pixels spread evenly.

## `scripts/spatial_overview/`

- **`overview_figure.py <image>`** runs binarize → skeleton → flaking exclusion → graph →
  curvature → anisotropy (no junctions) on the whole image and on each quadrant, timing both. It
  draws the 2×2 overview figure and updates `outputs/report.html`. Other grid sizes are rejected
  up front.
- **`attach_full_analysis.py <image>`** adds an existing `analyze_image --full-image` overlay
  and precedence picture to that image's HTML entry.

This is a "first look" at spatial variation, with no formal validation.
