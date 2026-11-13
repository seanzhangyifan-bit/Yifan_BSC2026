# Unified analysis: status

Running status for merging the crack-stats export, `analyze_image.py` and the spatial
overview into one tool. Branch: `unified-analysis`. Started 2026-11-13.

## Goal

One engine, one set of settings, one entry point for both the GUI and the command line,
so the user can choose:

- the calibration (µm per pixel)
- which part of the image to report on: whole image, centre, or chosen cells of an N×M grid
- which measurements and crack-stats column groups to include
- which figures to draw

Which engine settings (hyperparameters) the GUI exposes is still open. The user decides later.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| How regions are measured | The engine runs once on the whole image; results are cut per region. | Keeps one Otsu threshold and one flaking reference width per image, so cells are comparable and add up to the whole. |
| Spur cut-off and dark-speck limit | Stored in µm (9.15 µm) and µm² (48.3 µm²), converted with µm/px. | Their justification is a physical size. At 0.6098 µm/px they are exactly 15 px and 130 px. |
| Connectivity | Whole image only. Region rows leave it out; a grid or centre run writes it to an `image_connectivity` sheet. | Cutting at a region border splits the network, so per-region connectivity mostly reflects region size. |
| Segment quantities per region | Each segment goes whole to the region holding its middle pixel. | A segment cut by a border isn't counted as two short ones. |
| Pixel quantities per region | Only pixels inside the region count. | Cells add up to the whole image. |
| Old entry points | Replace and archive. | One way to run the analysis. |
| Per-segment output | Opt-in table: length, width, area. The four-method area bracket and the long console report go to the archive. | Keeps what's useful, drops what's hard to read. |

## Architecture

```
src/crackgraph/settings.py   AnalysisSettings: everything a user can change
src/crackgraph/regions.py    RegionSpec -> list of Region rectangles
src/crackgraph/engine.py     run_engine: binarize -> skeleton -> flaking -> graph, once per image
src/crackgraph/measures/     crack_stats.py, tortuosity.py, anisotropy.py, segments.py
src/crackgraph/analysis.py   analyze_image: settings + image -> one row per region
src/crackgraph/figures.py    overlay with regions, per-region panels, per-cell colour map
src/crackgraph/export.py     results.xlsx (regions, image_connectivity, segments, settings) + PNGs
src/analyze.py               command line
app.py                       GUI
```

## Done

- [x] New modules above, CLI and GUI (2026-11-13).
- [x] `skeletonize_and_prune` takes `dark_speck_area_px`; `OrientationSample` records its position;
  `anisotropy_from_samples` split out of `compute_anisotropy`; the crack-stats overlay can outline regions.
- [x] Parity check: whole image with default settings reproduces the old `compute_row` exactly on
  T2-M_H90_v1 (with flaking) and T5-M_H190_v1, 0 mismatched columns. A 3×3 grid's crack area adds
  up to the whole image. Locked in by `tests/test_unified_analysis.py` on a synthetic flaked grid.

- [x] Phase 1 committed (`1cf0971`).
- [x] Old entry points archived to `archive/thesis_export_old_entry_points_2026-11-13/` with their
  tests and walkthrough pages; the old exporter's output on the synthetic flaked grid frozen in
  `tests/data/old_exporter_flaked_grid.json` for the parity test.
- [x] `export_crack_stats_batch_bcd.py` and the two validation sweeps repointed; `corner_crop`
  moved into `regions.py` (same crop as before).
- [x] Docs: README, METHODOLOGY, CALIBRATION, GLOSSARY, the crack-stats schema (§1, §2, new §4d),
  walkthrough pages 5–11 and index, script READMEs, CHANGELOG.

## Still to do

- [ ] Decide which engine settings the GUI exposes (user's call). Candidates: the spur cut-off
  and dark-speck limit (already µm settings), the curvature and orientation windows, the flaking
  constants.
- [ ] Re-run `export_crack_stats_batch_bcd.py` to refresh `examples/crack_stats_batch_bcd.xlsx`
  (it predates the 2026-11-11 pruning changes).
- [ ] Optional: a real-image check of the grid figures on a dense image (only synthetic so far).
