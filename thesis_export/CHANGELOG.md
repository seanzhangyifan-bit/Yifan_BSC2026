# Changelog

Changes to this thesis code, newest first. Each entry says whether it changes any number the
pipeline reports, so you can tell which earlier outputs are still valid.

- **Changes results**: re-run affected outputs before reporting them.
- **No change to results**: earlier outputs are still valid.

Commit IDs link each entry to its full details in `git log`. Findings are numbered as in
[`docs/reviews/2026-11-11-full-code-review.md`](docs/reviews/2026-11-11-full-code-review.md).

## 2026-11-11

### Removed: T/Y junction classification, corner cross-check and precedence analysis

**Changes results** of the per-image analysis (`analyze_image.py`, GUI) only: those outputs lose
their junction-type, corner-check and precedence parts. **No change** to the crack stats
(`export_crack_stats.py`, `thesis_stats.xlsx`) or to any per-segment, curvature or anisotropy
number. These parts weren't mature enough to ship with the thesis.

- Deleted `junctions.py`, `corners.py`, `precedence.py`, their tests, and the three sweeps that
  tuned them (`window_sweep.py`, `corner_window_sweep.py`, `junction_tolerance_sweep.py`), plus
  `docs/junction_tolerance_sensitivity.md` and the July 2026 stage-4 review.
- `analyze_image.py`: the `--annulus-*`, `--y-angle-tol-deg`, `--t-*`, `--corner-*`,
  `--show-fit-detail`, `--hide-corner-check` and `--skip-junctions/-corner-cross-check/-precedence`
  options are gone; it no longer writes `_precedence.png` or `_overlay_detail.png`. The overlay
  shows endpoints and junctions (degree ≥ 3) only.
- The per-run spreadsheet (`--xlsx-out`) loses its T/Y/ambiguous and corner-agreement columns.
- GUI: the junction, corner-check and precedence checkboxes and the fit-detail option are gone.
- The validation gallery has 5 cases (curvature, anisotropy), down from 12.
- Junctions as graph nodes (degree ≥ 3, junction blobs, `n_junctions_deg3`) are unchanged.
- `METHODOLOGY.md`, `GLOSSARY.md`, `CALIBRATION.md`, the walkthrough (renumbered, pages 7–9
  removed) and the other docs no longer describe the removed parts. Findings 1, 12, 13 and 19 of
  the full code review, and the changelog entries for them, were taken out with them.
- Everything removed is kept: the git tag `archive/ty-precedence` holds the state before removal,
  and `archive/thesis_export_ty_precedence_2026-11-11/` at the repo root holds the original
  version of every file this change deleted or edited.

### Changed: the crack-stats export no longer selects images by file name

**Changes results** for the command-line export only: which images get a row. The numbers for any
given image are unchanged, except for the `_D_mm000000` bad frame (below).

`export_crack_stats.py` now gives a row to every image file (`.jpg`, `.jpeg`, `.png`, `.tif`,
`.tiff`, `.bmp`) under `--data-dir`, in any subfolder. Choosing which images belong in a table is
up to you: put only those in the folder, or upload them in the GUI, which never used these rules.

- Removed: the `*_mm000001.jpg` pattern (`RAW_GLOB`), the extra-image list (`ADDITIONAL_IMAGES`,
  for `23RH_PTFE_v1_mm000003.jpg`), the scale-bar skip list (`CONFIRMED_SCALE_BAR_IMAGES`, for
  `T5-M_H190_v2_mm000001.jpg`) and the bad-frame name check (`KNOWN_BAD_FRAME_SUBSTRINGS`). Pointed
  at the whole of `data/raw/`, the export now includes the `lu`/`ro` captures and the scale-bar
  image too, and a `_D_mm000000` frame would get (wrong) µm values instead of empty ones.
- `find_batch_images` → `find_images(data_dir, pattern="**/*")`.
- Schema doc §2 now describes the old rules as guidance for choosing images, not as rules the
  export applies; §6 and §7b, walkthrough page 5, the batch README and `METHODOLOGY.md` updated.

### Renamed: flaking area names use `px`

**No change to results**: names and wording only.

`MIN_CANDIDATE_AREA_PX2` → `MIN_CANDIDATE_AREA_PX`, `FlakingCandidate.area_px2` → `area_px`,
`FlakingResult.excluded_area_px2` → `excluded_area_px` (also in `cache_io.py`). The analysis
cache's `flaking_candidates.json` now uses the keys `area_px` and `excluded_area_px`, so cache
folders written before this change can't be loaded; re-run with `--cache-dir` to rebuild them.

### Removed: the two-pass flaking method; one crack-stats exporter

**Changes results**: every number from an image with flaking, in every tool. Images without
flaking are unchanged. Re-export before quoting.

The thesis export had two methods for flaked regions. The two-pass one skeletonized, removed
flaked patches from the mask, skeletonized again, and dropped edges within one crack width of the
cut from length/width stats only. The single-pass one skeletonizes once and omits every edge with
a pixel inside a flaked patch from the stats **and** the connectivity graph. Only the single-pass
method remains.

- `export_crack_stats_v3.py` is now `export_crack_stats.py` (the old two-pass exporter is gone);
  `export_crack_stats_v3_batch_bcd.py` is now `export_crack_stats_batch_bcd.py`. Default outputs
  drop the `_v3` suffix. `compute_row` keeps the GUI's `on_stage` progress hook; the stage order
  is now binarize, skeletonize, flaking.
- `analyze_image.py` and the spatial overview figure skeletonize once
  and remove flake-touching edges from the skeleton before analysis
  (`flaking.remove_flake_touching_edges`, new). `analyze_image`'s report line is now "Skeleton
  edges touching a flaked region, removed before graph analysis".
- Removed: `flaking.cut_adjacent_path_indices`, `CUT_ADJACENT_BUFFER_WIDTH_MULTIPLIER`, the
  `exclude_from_stats` option and `near_flaking_cut` fields/CSV column in `edge_metrics.py`. The
  crack-stats overlay highlights omitted edges instead of cut-adjacent ones.
- Spreadsheet column `flaking_n_edges_excluded_near_cut` no longer exists; `flaking_n_edges_omitted`
  replaces it. The export now always includes the six `runtime_*` columns.
- Tests: `test_export_crack_stats_v3.py` → `test_flaking_omission.py` (+2 tests for the new
  helper); one entry-point test and one edge-metrics test for removed features dropped.
- Docs: schema doc §1, §4, §4b, §9 rewritten, §10 (method comparison) removed; walkthrough pages
  3, 5, 6, 11, 12, 14; batch README; `examples/` keeps only `crack_stats_batch_bcd.xlsx`
  (renamed) and the validation gallery.

### Terminology: dark specks are removed, bright spots are filled

**No change to results**: wording only, in docs, comments, figure labels and two test names.

- **Dark specks**: pieces of catalyst layer or dust sitting inside a crack. They are **removed**
  (`remove_small_holes`, `DARK_SPECK_AREA_PX`).
- **Bright spots**: light shining through the catalyst layer, outside cracks. They are **filled**
  (`remove_small_objects`, `min_object_px`). Previously called "bright specks" and described as
  removed.

### Changed: host-stub pruning replaces the corner test; dark-speck removal raised to 130 px

**Changes results**: edge counts and edge-length statistics (`ledge`, `ledge,gc`,
`avg_edge_length_px`) on dense images with wide cracks; small shifts in total length. Re-run every
crack-stats export before quoting these numbers.

Two changes to stage 2 (`skeleton.py`), made together:

1. **Host-stub rule.** A dead end is now removed if less than `spur_px` (15 px = 9.1 µm) of its
   length lies outside the crack it branches from. This replaces the correlation test (width
   rising steadily along a branch, correlation > 0.99), which missed many stubs from a wide
   crack's centre line to bumps on its wall (correlation 0.94–0.99) and removed some real cracks
   cut off by the image edge. `CORR_THRESHOLD` and `MIN_LEN_FOR_CORR_PX` are gone; the rule uses
   only `spur_px`. Tested against two other variants (`docs/design_notes.md`).
2. **Dark-speck removal 50 → 130 px**, renamed `HOLE_AREA_THRESHOLD_PX2` → `DARK_SPECK_AREA_PX`.
   130 px is the area of a d90 ≈ 7.8 µm agglomerate (inks T2–T4). Removes loops around specks
   inside wide cracks.

**Measured on 2048 px centre crops of 6 micrographs** (no flaking exclusion):

| Image | Edges | `ledge` | Length | `wcrack` | `N` |
|---|---|---|---|---|---|
| T3-PTFE_v1 | −16.4% | +22.5% | −2.5% | +1.0% | same |
| T4-M_H95_v1 | −11.5% | +13.7% | −1.5% | +1.4% | same |
| T5-PTFE_H95_v1 | −4.7% | +6.1% | −0.8% | same | same |
| 23RH_NR212_v1 | −2.1% | +3.9% | −0.1% | same | same |
| T3-M_v1 | +3.0% | −0.9% | +0.6% | same | same |
| T5-M_H190_v1 | same | same | +0.2% | same | same |

**Measured on the 19 thesis images, full size, with flaking exclusion** (same code before and
after except this change; `outputs/reexport_2026-11-11/` in the working copy):

- `ledge`: T4-M +16% (both replicates), T5-PTFE_H145 +8%, all other images −1 to +4%.
  `ledge,gc` moves the same way.
- `crack`, `flaking`, `N`: unchanged (≤ 0.7%). `wcrack`: ≤ 2.9% (T4-M).
- `fgc` and `dgc`: unchanged except T5-PTFE_H50_v1 (−10.9% and −7.8%), the sparsest image (a
  handful of edges), where one removed stub changes the giant component.
- No ranking within a comparison group changes, except 0RH vs 23RH NR212, which were tied before
  (`ledge` 127.6 vs 128.0 µm) and stay within their replicate spread (13–15%).

- **Affected outputs**: `n_edges`, `ledge`, `ledge,gc`, `avg_edge_length_px`, total length,
  loop and junction counts. Spreadsheet column `n_corner_artifacts_pruned` is renamed
  `n_host_stubs_pruned` and counts a different rule. `analyze_image`'s
  `--corner-artifact-corr-threshold` is replaced by `--no-host-stub-pruning`.
- **Not affected (on these crops)**: crack area, flaking area, `N`; `wcrack` within 1.4%.
- `SkeletonResult` fields renamed: `n_host_stubs_pruned`, `pruned_host_stub_lengths`,
  `prune_host_stubs`; pruned-branch reason `"corner_artifact"` → `"host_stub"`.

### Corrected: what the "skeleton loop" metric measures

**No change to results**: documentation only; no code or number changed.

The docs said thinning sometimes "traces both walls" of a wide crack and leaves a fake loop, and
that `skeleton_loop_sweep.py` measures this (0–55% of edges per image). That is wrong:
`skeletonize()` preserves topology, so a loop needs a hole in the mask. A check on 2048 px centre
crops of all 41 `*_mm000001` images found:

- Mask holes equal graph cycles on 33 of 41 images; the other 8 have 1–5 extra cycles, most
  likely zero-area pixel cycles where the skeleton is 2 px thick.
- Of the 370 short junction-to-junction edges the sweep counts, only 30 (8%) lie next to a dark
  speck, i.e. a real small loop. The rest are short segments between closely spaced junctions:
  split crossings or real geometry (not yet checked by eye).

The sweep's numbers still describe how many short edges inflate `n_edges`; only their cause was
misdescribed. Corrected in `docs/design_notes.md`, `docs/batch_stats/crack_stats_schema.md` §4,
the `skeleton.py` and `skeleton_loop_sweep.py` docstrings, `scripts/validation/README.md` and
walkthrough pages 2, 4 and 14.

### Documented: physical justification for the spur cut-off

**No change to results**: `SPUR_PX_PLACEHOLDER` stays 15 px; only its documentation changed.

15 px = 9.1 µm on `mm` images, about the largest measured agglomerate size (d99 of inks T2–T4,
7–10 µm, laser diffraction) and the typical film thickness (8–16 µm). A shorter dead end can't
be told apart from crack-wall roughness. The value was chosen first and checked against these
scales afterwards. Status 🔴 → 🟢 in `CALIBRATION.md`; full sources and caveats in
`docs/calibration_notes.md`.

### Removed: foreground-fraction sanity band in binarize

**No change to results**: no measured number changes. The per-image spreadsheet loses three
columns.

`binarize()` used to flag images whose crack share fell outside 1%–15%. It was only a warning;
no later step read it. The band was never derived, and 23 of 39 batch images fell outside it
(see `docs/batch_stats/crack_stats_schema.md` §7), so it flagged normal variation.

- **Removed**: the `sanity_band` argument and the `sanity_ok`/`sanity_band` result fields; the
  `--otsu-sanity-band` option and PASS/FAIL line in `analyze_image`; the `binarize_sanity_ok`,
  `binarize_sanity_band_lo` and `binarize_sanity_band_hi` spreadsheet columns.
- **Kept**: `foreground_fraction`, still printed and still in the spreadsheet.

The entries down to "Added: entry-point smoke tests" are one bug-fix pass (review findings 9,
11, 13–19). All 174 tests pass.

### Fixed: giant-component share read low when two segments join the same junctions

**Changes results**: `giant_component_fraction` in every crack-stats export (v1, v2 and v3).
Review finding 17.

The exporters built the crack network as a `networkx.Graph`. When two different segments join
the same two junctions, such as the two sides of a small cell, a `Graph` keeps only one of them.
The giant component's length came out short, while the total length counted both, so the share
read low. The network is now a `MultiGraph`, which keeps every segment.

On the 41-image thesis batch: 27 of 41 images have at least one such pair. On 17, the value rises
at the 4th decimal place or above; the largest rises are 75RH_PTFE_v1 (0.9907 → 0.9973), T3-PTFE_v1
(0.9732 → 0.9784) and T4-M_H95_v1 (0.9937 → 0.9988). No image's giant component changed. These
shifts are small next to the differences between conditions, but any `fgc` value quoted from an
older export should be re-run.

- **Affected outputs**: `giant_component_fraction` (thesis notation `fgc`). The shipped example
  spreadsheets in `examples/` predate this fix.
- **Not affected**: `n_components`, and every length, width and area column.

### Fixed: overview figure counted flaked patches as crack

**Changes results**: overview figures of images with flaking. Review finding 18.

`overview_figure.py` skipped the flaking exclusion that every other entry point runs, so a
flaked patch's own interior skeleton went into the rose diagrams and tortuosity histograms.
It now runs the same two-pass exclusion as `analyze_image.py`.

### Fixed: per-image totals included segments cut short by the flaking correction

**Changes results**: `analyze_image.py`'s console totals on images where a flake touches the
analysed region. Review finding 15.

The batch exporter leaves segments next to a flaking cut out of its length and width numbers,
because our own correction cut them short. `analyze_image.py` didn't, so the two disagreed on
flaked images. Now:

- Total length, the width counts, the length-weighted mean width and the length density leave
  those segments out. The report says how many there were and their total length.
- The edge-metrics CSV keeps every segment and has a new `near_flaking_cut` column.
- Area totals are unchanged; those pixels are real crack.

Neither of the two corner crops checked touches a flake, so both reports came out unchanged.
The per-run spreadsheet row (`--xlsx-out`) doesn't use these totals.

### Fixed: one validation-gallery row always said PASS

**No change to results.** Review finding 14.

The dominant-direction row of `anisotropy_aligned` now checks the measured direction against the
test suite's 10° tolerance. `examples/validation_gallery.html` was regenerated: 12/12 pass, with
178.3° measured against 0° expected (1.7° apart on the 0–180° circle).

### Fixed: overview script accepted grid sizes it can't draw

**No change to results.** Review finding 11.

`--n-rows`/`--n-cols` other than 2×2 used to run the whole analysis, then crash while drawing.
They're now rejected before anything runs.

### Changed: per-image analysis about 3× faster on full images

**No change to results** (checked). Review finding 9.

- Segment areas are counted in one pass over the image instead of one pass per segment.
- A second step, since removed from this export, was sped up the same way.

On a full T5 image, `analyze_image --full-image` went from 194 s to 61 s. The report and the
edge table (1,853 segments) came out identical.

### Changed: small consistency fixes

**No change to results**, except the console wording noted below. Review findings 15 and R5.

- The console now uses the spreadsheet's anisotropy cut-off (0.15, was 0.2) to say "dominant
  direction not meaningful". An image between 0.15 and 0.2 no longer gets both "intermediate"
  and "no preferred direction".
- `curvature.py` defines its `ok` flag; overlays look segments up by their ID rather than their
  position in the table; `cache_io.py` states when a recomputed width map can differ.
- Deleted an unused helper (`_chord_scan.suppress_non_max`).
- The walkthrough's line numbers now match the code.

### Added: entry-point smoke tests

**No change to results.** Review finding 16.

`tests/test_entry_points.py` runs `analyze_image.py`, both crack-stats `compute_row`s, the
overview figure, `region.py` and the GUI on a small synthetic grid with a flake. It checks that
they run and write their files, not their numbers. The broken v3 import found in October would
have failed here.

### Changed: per-image results say they cover a corner sample

**No change to results** (labels only). Review finding 10.

By default the per-image analysis looks at a top-left corner crop, **about 1.5% of each image**,
while the crack stats cover the whole image. Corner numbers could be mistaken for
whole-image numbers. Now:

- The console report states the region and its area share at the top. The spreadsheet's `region_description` column carries the same text.
- The GUI labels every result with its region, and shows a note when corner and whole-image
  results appear together.
- README, `METHODOLOGY.md` and the walkthrough say the same.

### Added: code walkthrough

**No change to results** (documentation only).

[`docs/walkthrough/`](docs/walkthrough/README.md): a 14-page, plain-language tour of every part of
the code, in the order data flows through it, function by function with line references.

### Fixed: batch exports couldn't find images; scale-bar claim no longer automatic

**No change to results.** Commit `71b9557`, review findings 2 and 3.

- The batch export scripts looked for images only in `data/raw/` inside this folder, which isn't
  bundled, and crashed. They now take `--data-dir <folder>` and stop with a clear message if no
  images are found. With `--data-dir ../data/raw`, they select the same 41 images as before.
- Every spreadsheet row used to say the scale bar was "visually confirmed", even for unchecked
  images uploaded to the GUI. The `scale_bar_check` column now says `not checked` unless you pass
  `--scale-bars-checked`.

To regenerate the thesis spreadsheets, run (from this folder):

```
python3 -m scripts.batch_stats.export_crack_stats --data-dir ../data/raw --scale-bars-checked
```

### Fixed: documentation out of date

**No change to results.** Commit `2dcf0d3`, review findings 4–8.

- Removed leftover mentions of the deleted kink-detection feature, and corrected the validation
  gallery's size to 12 cases across 4 measurement methods.
- Regenerated `examples/validation_gallery.html` (12/12 cases pass).
- `CALIBRATION.md`: removed stray backslashes from the settings table and corrected line numbers
  there and in `docs/calibration_notes.md`. Totals are now 3 🟡, 15 🔴.
- Updated 59 file paths that predated the folder reorganisation.
- Corrected two descriptions of the flaking step: the v3 spreadsheet's definitions sheet, and a
  label in the per-image console report.

### Added: full code review

Commit `3f0a0d9`. [`docs/reviews/2026-11-11-full-code-review.md`](docs/reviews/2026-11-11-full-code-review.md)
lists every finding, its severity, and its fix status. Findings 9–16 and the readability items are
still open.

### Changed: shorter module descriptions in `skeleton.py` and `flaking.py`

**No change to results.** Commit `93ab124`.

The long opening descriptions are now about 15 lines each. The full original text moved,
unchanged, to [`docs/design_notes.md`](docs/design_notes.md).

## 2026-10-11

### Changed: core crack-stats code tidied; v3 exporter fixed

**No change to results.** Commit `08d6e83`.

- The exporter reuses the crack-width map that the skeleton step already computes, instead of
  recalculating it. This saves about 13 seconds per full-size image, and output was checked
  identical on two real images.
- One shared helper replaces four copies of the same pixel-lookup code.
- The v3 exporter and its batch runner no longer crash on start; their import paths predated the
  folder reorganisation.

## 2026-10-10

### Removed: kink detection

**Changes results** (removes outputs). Commit `58682f6`.

Removed the kink-detection module and its tests, and cleaned up the docs. Outputs from before this
date may include kink counts that this version no longer produces.

## 2026-08-12

### Added: this standalone folder and the local GUI

Commits `3fe6802`, `ac387de`. First version of `thesis_export/`, a standalone copy of the analysis
code organised by deliverable, plus the Streamlit GUI (`app.py`).
