# Changelog

Newest first. Each entry is tagged:

- **Results changed**: re-run affected outputs before quoting them.
- **Results unchanged**: earlier outputs stay valid.

Details of any entry: `git log`.

## 2026-11-14

### Added: debug view; GUI progress and layout fixes
**Results unchanged** (figures and GUI only).
- New `debug` figure (`src/crackgraph/debug_figure.py`; GUI checkbox, `--figures debug`):
  pruned branches by reason, dark specks removed, bright spots filled, flaking and the
  binarized boundary, on the whole image and four full-resolution close-ups.
- GUI progress bar: the analysis runs in a worker thread, so the elapsed time ticks, the bar
  moves during long steps, and it shows an estimate of the time left.
- GUI upload box: clearer heading and drag-and-drop instructions.
- Rose/tortuosity panels: titles no longer overlap the angle labels or the figure title.
- Compare images: the board sends its changes only when you click **Update table and plot**,
  and the section redraws on its own (a Streamlit fragment), so the page no longer greys out
  after every drag. The board frame no longer leaves blank space below it.
- Replicates plot: "Mean ± error bar" style (SD or SEM, sample statistics), editable y-axis
  label, y-axis from 0 by default with optional min/max, and n labels moved above the plot
  area so they never cover points.

## 2026-11-13

### Added: Compare images in the GUI
**Results unchanged** (no measurement touched; the workbook gains an optional `labels` sheet).
- A drag-and-drop board after a run: name the factors you varied, sort images into cells
  (replicates share a cell), optionally pre-sort by file name. Works with any folder or naming
  scheme.
- Below it: a labels table and a replicates plot (dot per image; mean bar only when n ≥ 2;
  n = 1 marked in red).
- Run results now stay in the session, so they survive interaction with the page.
- New: `src/crackgraph/grouping.py`, `src/crackgraph/gui/`, `tests/test_grouping.py`, one more
  test in `tests/test_entry_points.py`. Docs: walkthrough page 10.

### Removed: `scale_bar_check` column
**Results unchanged** (one identification column gone).
- It only recorded a manual check (`--scale-bars-checked`); the tool never detected scale bars.
- `--scale-bars-checked` removed from `src/analyze.py` and the batch script. The schema doc now
  says input images must not carry a scale bar; columns 6–26 are renumbered 5–25.
- Evidence tags and calibration colours are now described as heuristics.

### Removed: anisotropy index
**Results changed**: the `anisotropy_index` and `dominant_bearing_deg` columns are gone.
- Reason: one index can't tell an orthogonal grid from random directions, which was confusing.
- The rose plot (length-weighted direction histogram) stays and is the anisotropy result.
- Tests and validation cases now check the histogram directly. Tolerances come from 8 seeds per
  synthetic field (`tests/test_anisotropy.py`).
- `examples/validation_gallery.html` regenerated: 5/5 pass.

### Archived: code review and experimental material
**Results unchanged.**
- `docs/reviews/`, `docs/experimental/` and `scripts/experimental/` moved to
  `archive/thesis_export_reviews_experimental_2026-11-13/` (repo root).

### Changed: one analysis tool with user-chosen settings and regions
**Results unchanged** for whole-image crack stats with default settings (identical on
T2-M_H90_v1 and T5-M_H190_v1; checked by `tests/test_unified_analysis.py`).
**Results changed** slightly for tortuosity, curvature and orientation: flake-touching segments
are now left out without rebuilding the graph, as in the crack stats.
- Replaces the crack-stats exporter, `analyze_image.py` and the spatial overview with:
  `engine.py` (runs once per image), `regions.py`, `measures/`, `settings.py`, `src/analyze.py`
  (command line) and a rewritten `app.py` (GUI).
- New settings: µm per pixel; whole image, centre or chosen grid cells; measurements and
  crack-stats column groups; figures.
- Spur cut-off and dark-speck limit stored in µm (9.15 µm, 48.3 µm²). At 0.6098 µm/px they're
  exactly 15 px and 130 px.
- Connectivity: whole image only. Grid and centre runs write it to an `image_connectivity` sheet.
- New columns `region`, `region_rows_px`, `region_cols_px`, `region_area_pct`; new `settings`
  sheet; runtime columns opt-in; `runtime_stats_s` → `runtime_measure_regions_s`.
- Per-segment table: length, width, one area estimate.
- Archived to `archive/thesis_export_old_entry_points_2026-11-13/`: the old entry points, the
  four-method area bracket (`edge_metrics.py`), the HTML and per-run xlsx reports, the analysis
  cache, the corner-crop default, and their tests and walkthrough pages.
- Removed `flaking.remove_flake_touching_edges` (unused).
- `METHODOLOGY.md`: threshold is global Otsu (said "adaptive").

### Archived: design and calibration notes
**Results unchanged.**
- `docs/design_notes.md` and `docs/calibration_notes.md` → `archive/thesis_export_notes_2026-11-13/`.
  The walkthrough covers the same rationale.
- Schema doc: removed "Choosing images from the thesis image set" (the tool doesn't select by
  file name).

## 2026-11-11

### Removed: T/Y junction classification, corner cross-check, precedence analysis
**Results changed** for the per-image analysis only (those outputs are gone). Crack stats,
per-segment, curvature and anisotropy numbers unchanged.
- Not mature enough for the thesis.
- Deleted the modules, their tests, their three sweeps, the sensitivity doc, and the matching
  options, outputs and GUI checkboxes. Validation gallery: 12 → 5 cases.
- Junctions as graph nodes (degree ≥ 3) are unchanged.
- Kept in git tag `archive/ty-precedence` and `archive/thesis_export_ty_precedence_2026-11-11/`.

### Changed: crack-stats export no longer selects images by file name
**Results changed**: which images get a row. Per-image numbers unchanged.
- Every image file (`.jpg .jpeg .png .tif .tiff .bmp`) under `--data-dir` gets a row.
- Removed the `*_mm000001.jpg` pattern, the extra-image list, the scale-bar skip list and the
  bad-frame check. Choosing images is up to you.

### Renamed: flaking area names use `px`
**Results unchanged.**
- `MIN_CANDIDATE_AREA_PX2` → `MIN_CANDIDATE_AREA_PX`; `area_px2` → `area_px`;
  `excluded_area_px2` → `excluded_area_px`.

### Removed: two-pass flaking method
**Results changed**: every number from an image with flaking, in every tool.
- Only the single-pass method remains: skeletonize once; omit every segment with a pixel in a
  flaked patch from the stats and the connectivity graph.
- `export_crack_stats_v3*.py` → `export_crack_stats*.py`; `flaking_n_edges_excluded_near_cut` →
  `flaking_n_edges_omitted`.

### Terminology: dark specks removed, bright spots filled
**Results unchanged.**
- Dark specks (catalyst layer or dust inside a crack): removed (`remove_small_holes`).
- Bright spots (light through the catalyst layer): filled (`remove_small_objects`).

### Changed: host-stub pruning replaces the corner test; dark-speck limit 50 → 130 px
**Results changed**: segment counts and lengths (`ledge`, `ledge,gc`) on dense, wide-crack images.
- Host-stub rule: a dead end is removed if less than `spur_px` (15 px = 9.1 µm) lies outside the
  crack it branches from. Replaces the width-correlation test, which missed many stubs and removed
  some real cracks.
- Dark-speck limit 130 px = area of a d90 ≈ 7.8 µm agglomerate (inks T2–T4). Renamed
  `HOLE_AREA_THRESHOLD_PX2` → `DARK_SPECK_AREA_PX`.
- `n_corner_artifacts_pruned` → `n_host_stubs_pruned` (counts a different rule).
- Effect on the 19 thesis images (full size, with flaking exclusion):
  - `ledge`: T4-M +16%, T5-PTFE_H145 +8%, others −1 to +4%.
  - `crack`, `flaking`, `N`: ≤ 0.7%. `wcrack`: ≤ 2.9%.
  - `fgc`, `dgc`: unchanged except T5-PTFE_H50_v1 (−10.9%, −7.8%), the sparsest image.
  - No ranking within a comparison group changes, except 0RH vs 23RH NR212, tied before and
    still within replicate spread.

### Corrected: what the "skeleton loop" metric measures
**Results unchanged** (docs only).
- Thinning can't create a loop without a hole in the mask. Of the short junction-to-junction
  edges counted, only 8% lie next to a dark speck; the rest are short segments between close
  junctions.

### Documented: physical basis of the spur cut-off
**Results unchanged.**
- 15 px = 9.1 µm ≈ largest agglomerates (d99 of inks T2–T4, 7–10 µm) and film thickness
  (8–16 µm). Chosen first, checked afterwards. 🔴 → 🟢.

### Removed: foreground-fraction sanity band
**Results unchanged**; three spreadsheet columns gone.
- The 1–15% band was never derived and flagged 23 of 39 normal images. `foreground_fraction` is
  kept.

### Fixed: giant-component share read low
**Results changed**: `giant_component_fraction` (`fgc`).
- Two segments joining the same two junctions were counted once. Now a `MultiGraph`.
- 17 of 41 images change at the 4th decimal or above; largest: 75RH_PTFE_v1 0.9907 → 0.9973.

### Fixed: smaller bugs
- Overview figure skipped flaking exclusion. **Results changed** (overview figures, since
  archived).
- Per-image totals included segments cut short by the flaking correction. **Results changed**
  (per-image console totals, since archived).
- A validation-gallery row always said PASS. **Results unchanged.**
- Overview script accepted grid sizes it couldn't draw. **Results unchanged.**

### Changed: smaller improvements
**Results unchanged.**
- Per-image analysis about 3× faster on full images (194 s → 61 s, identical output).
- Entry-point smoke tests added.
- Per-image results labelled with the region they cover.
- Code walkthrough added (`docs/walkthrough/`).
- Batch exports take `--data-dir`; `scale_bar_check` says `not checked` unless you pass
  `--scale-bars-checked`.
- Outdated docs fixed (stale paths, line numbers, removed features).
- Shorter module descriptions in `skeleton.py` and `flaking.py`.

## 2026-10-11

### Changed: crack-stats code tidied
**Results unchanged** (checked on two images).
- Reuses the skeleton step's width map (about 13 s faster per image).
- One shared pixel-lookup helper instead of four copies.

## 2026-10-10

### Removed: kink detection
**Results changed** (kink outputs gone).

## 2026-08-12

### Added: this folder and the GUI
- First standalone copy of the analysis code, plus the Streamlit GUI (`app.py`).
