# Changelog

Changes to this thesis code, newest first. Each entry says whether it changes any number the
pipeline reports, so you can tell which earlier outputs are still valid.

- **Changes results**: re-run affected outputs before reporting them.
- **No change to results**: earlier outputs are still valid.

Commit IDs link each entry to its full details in `git log`. Findings are numbered as in
[`docs/reviews/2026-11-11-full-code-review.md`](docs/reviews/2026-11-11-full-code-review.md).

## 2026-11-11

### Changed: junction results say they cover a corner sample

**No change to results** (labels only). Review finding 10.

By default the per-image analysis looks at a top-left corner crop, **about 1.5% of each image**,
while the crack stats cover the whole image. Corner junction counts could be mistaken for
whole-image numbers. Now:

- The console report states the region and its area share at the top and next to the junction
  counts. The spreadsheet's `region_description` column carries the same text.
- The GUI labels every result with its region, and shows a note when corner and whole-image
  results appear together.
- The sensitivity sweep's CSVs have a `region_area_pct` column. A re-run gave identical counts.
- README, `METHODOLOGY.md`, the sensitivity write-up and the walkthrough say the same.

### Added: code walkthrough

**No change to results** (documentation only).

[`docs/walkthrough/`](docs/walkthrough/README.md): a 14-page, plain-language tour of every part of
the code, in the order data flows through it, function by function with line references.

### Added: sensitivity check for the T/Y junction cut-offs

**No change to results** (adds an analysis). Review finding 12.

New script `scripts/validation/junction_tolerance_sweep.py` re-sorts each image's measured
junction angles under 17 cut-off settings. Results in
[`docs/junction_tolerance_sensitivity.md`](docs/junction_tolerance_sensitivity.md), on 41 images
(corner crop):

- At the current cut-offs, 67% of junctions are ambiguous, 26% T, 7% Y.
- Absolute T share ranges 9–45% as all cut-offs go from ×0.5 to ×1.5. The Y count ranges 6–208.
- Ranking conditions by T share holds for ±5° / ±25% changes (rank correlation 0.82–0.98).

**Affects how you report junction counts**: report absolute T/Y numbers with a range, not as
fixed values, and check that any comparison between conditions keeps its direction across the
tested cut-offs.

### Fixed: corner cross-check read west-pointing cracks as east-pointing

**Changes results** (corner cross-check and precedence agreement only). Commit `65d1ed9`,
review finding 1.

The corner cross-check combined two angle readings with a plain average. Two readings of a
west-pointing crack wall, such as 179° and −179°, averaged to 0°, which points east. On synthetic
T-junctions near west, this flipped the crack's direction in 9 of 20 runs while still reporting
agreement with the main method.

Both averages now go the short way around the circle. Two regression tests were added.

- **Affected outputs**: the corner cross-check's agree/disagree counts, and the "both methods
  agree" support in the precedence graph, on images with roughly east–west cracks.
- **Not affected**: skeletons, crack stats, and the main method's T/Y labels.

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
