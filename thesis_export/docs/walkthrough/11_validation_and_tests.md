# 11. Validation and tests

How do we know the measurements are right? A micrograph has no answer key, so this project makes
its own: **synthetic images** drawn by code, where the true lengths, directions and counts are known
exactly. Real images are then used to measure *sensitivity*: how much results move when a
setting changes.

| Where | What |
|---|---|
| `src/crackgraph/synthetic.py` | Draws synthetic crack patterns with known answers |
| `src/crackgraph/synthetic_degradation.py` | Makes them messier: uneven lighting, JPEG artefacts, debris |
| `src/crackgraph/validation_cases.py`, `validation_report.py` | The 5-case visual validation gallery |
| `scripts/validation/` | Galleries, setting sweeps and sensitivity checks |
| `tests/` | 142 automatic checks; run with `python3 -m pytest tests/` |
| `scripts/experimental/` | An unvalidated idea, kept for the record |

---

## `synthetic.py`: patterns with known answers

Each `generate_...` function returns a grayscale image: bright cracks (230) on a dark background
(10). Where possible, a matching `..._ground_truth` or `..._topology` function gives the exact
expected answer from the same parameters. The image itself never carries its answer.

| Generator | Shape | Used to check |
|---|---|---|
| `generate_t_junction`, `generate_y_junction` | One T-shaped or Y-shaped meeting of three arms | Three-way meetings in the graph; curvature of straight arms |
| `generate_curved_t_junction` | A straight stem meeting a circular arc | Curvature = 1/radius |
| `generate_double_t_junction` | Two T shapes close together | Neighbouring junctions in the graph |
| `generate_straight_line`, `generate_kinked_line` | One line, straight or bent once | Curvature and tortuosity |
| `generate_oriented_segment_field` | Many separate segments with controlled directions | Anisotropy |
| `generate_grid`, `generate_wavy_grid`, `generate_hexagonal_grid` | Meshes with exactly known node and segment counts | Graph topology and total length |
| `generate_grid_with_flakes` | A grid with filled circles stamped on | Flaking detection |
| `generate_tapered_line` | A crack that thins and fades at both ends | Width and area on tapering tips |
| `generate_converging_lines` | Two lines that gradually merge | The smallest separable gap |
| `generate_hierarchical_network` | Brick-pattern primary cracks plus secondary T's | A realistic network with known structure |
| `generate_crescent_scale_pattern` | Overlapping crescent tiles | Area and perimeter of filled shapes |
| `generate_density_gradient_field` | Segments getting denser left to right | Density across zones |

Optional `jitter_px` adds wobble to the edges, with a fixed random seed, so repeated runs give
identical images.

## `synthetic_degradation.py`

| Function | What it simulates |
|---|---|
| `apply_illumination_gradient` | Uneven lighting across the image |
| `apply_jpeg_blocking` | A real low-quality JPEG save and reload |
| `apply_debris` | Small dark specks interrupting cracks |

Degraded images have **no exact answer**, so results are reported as "clean vs degraded"
differences rather than pass/fail. None of these effects has been seen in your real images;
they're precautionary checks, labelled `[speculated]`.

## The validation gallery

- **`validation_cases.py`** defines 5 cases:
  - 2 curvature
  - 3 anisotropy
- Each case draws a synthetic image, runs the real pipeline, saves its overlay or rose plot, and
  builds an expected-vs-measured table.
- The pass/fail tolerances are copied from the matching tests, with a comment pointing to them.
- **One case shows a known weakness on purpose**: the anisotropy blind spot on an orthogonal
  grid.
- **`validation_report.py`** turns the results into one HTML page.
- Run it with `python3 -m scripts.validation.validation_gallery`. A ready-made copy is in
  `examples/validation_gallery.html`.

Every row is a real check. The dominant direction in `anisotropy_aligned` must lie within 10° of
0° on the 0–180° circle, the same tolerance as `tests/test_anisotropy.py`.

## `scripts/validation/`

| Script | Kind | What it shows |
|---|---|---|
| `curvature_window_sweep.py` | Setting sweep | Picks the curvature window (10 px) against arcs of known radius. |
| `segmentation_sensitivity_sweep.py` | Sensitivity, real image | How much results move if the crack/not-crack threshold changes. |
| `skeleton_loop_sweep.py` | Measurement, real images | How common short junction-to-junction edges are, per image (mostly close junctions, not loops; see `02_skeleton.md`). |
| `validation_gallery.py` | Gallery | The 5-case page above. |
| `crack_stats_synthetic_gallery.py` | Gallery | Synthetic grids and flakes through the crack-stats path, expected vs measured. |
| `synthetic_benchmark_raw_gallery.py`, `synthetic_benchmark_report.py` | Gallery | A 9-case benchmark: first the raw images with exact answers, then the measured results. |
| `pipeline_stage_figures.py` | Figures | Step-by-step panels from raw image to final graph, for a real image. |

The **sweeps** justify the 🟡 settings in `CALIBRATION.md`. The **sensitivity** checks don't pick
a value; they show how much a 🔴 setting matters.

## `tests/`

14 files, 101 tests (a few tests run several cases each). All pass. Each checks one module against synthetic cases with known
answers, or checks a fixed bug stays fixed. Run them from `thesis_export/` with `python3 -m pytest tests/`.

| Test file | Tests | Covers |
|---|---|---|
| `test_skeleton.py` | 7 | Pruning, the host-stub rule and dark-speck removal (page 2) |
| `test_grid_synthetic.py` | 9 | Topology on meshes, flaking on synthetic flakes (pages 3–4) |
| `test_flaking_omission.py` | 5 | Omitting segments that touch a flaked region (page 3) |
| `test_unified_analysis.py` | 8 | Settings, regions and the whole-image row against the old exporter's frozen output (pages 5–7) |
| `test_crack_stats_measure.py` | 9 | Crack-stats helpers, incl. parallel segments in the network, and per-region counting (page 7) |
| `test_curvature.py`, `test_anisotropy.py` | 7 + 7 | Page 8 |
| `test_entry_points.py` | 3 | The command line and the GUI run end to end on a small synthetic flaked grid (page 10) |
| `test_summary_plots.py` | 4 | Rose and histogram drawing (page 9) |
| `test_synthetic*.py` | 1 + 21 + 11 | The generators, and the 9-case benchmark through the pipeline |
| `test_validation_*.py` | 3 + 6 | The validation gallery |

`tests/fixtures/old_exporter_flaked_grid.json` holds the old crack-stats exporter's output on the
synthetic flaked grid, frozen when it was archived (2026-11-13).

The entry-point smoke tests (review finding 16) check that each entry point runs, not its
numbers; the library tests above cover those.

## `scripts/experimental/tracing_poc.py`

A throwaway proof of concept for a faster way to trace crack centre lines without
skeletonizing. It belongs to the in-situ drying-video idea in
`docs/experimental/dynamic_tracking_hypothetical.md`. It tests only three simple synthetic shapes
(a triangle, a rectangle and an L-shape), and is **not validated and not connected to the pipeline**.
