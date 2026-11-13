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

## Still to do

- [ ] Commit this phase.
- [ ] Archive the old entry points: `scripts/batch_stats/export_crack_stats.py` (after moving its
  helpers' tests to `measures/crack_stats.py`), `src/analyze_image.py`, `scripts/spatial_overview/`,
  `region.py`, `tiling.py`, `html_report.py`, `xlsx_report.py`, `cache_io.py` if unused, and their tests.
- [ ] Repoint `export_crack_stats_batch_bcd.py`, `add_definitions_sheet.py` and the validation
  scripts that import `region.default_corner_crop`.
- [ ] Docs: README, METHODOLOGY, the crack-stats schema (new region columns, connectivity sheet),
  walkthrough pages 5 and 8–10, GLOSSARY, CHANGELOG entry.
- [ ] Decide which engine settings the GUI exposes.
- [ ] Note for the CHANGELOG: tortuosity and anisotropy now leave out flake-touching segments
  without rebuilding the graph, as crack stats do. Before, `analyze_image` rebuilt the graph, which
  could merge segments, so their numbers can differ slightly from older runs.
