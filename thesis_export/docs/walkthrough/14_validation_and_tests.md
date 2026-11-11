# 14. Validation and tests

How do we know the measurements are right? A micrograph has no answer key, so this project makes
its own: **synthetic images** drawn by code, where the true angles, lengths and counts are known
exactly. Real images are then used to measure *sensitivity*: how much results move when a
setting changes.

| Where | What |
|---|---|
| `src/crackgraph/synthetic.py` | Draws synthetic crack patterns with known answers |
| `src/crackgraph/synthetic_degradation.py` | Makes them messier: uneven lighting, JPEG artefacts, debris |
| `src/crackgraph/validation_cases.py`, `validation_report.py` | The 12-case visual validation gallery |
| `scripts/validation/` | Galleries, setting sweeps and sensitivity checks |
| `tests/` | 162 automatic checks; run with `python3 -m pytest tests/` |
| `scripts/experimental/` | An unvalidated idea, kept for the record |

---

## `synthetic.py`: patterns with known answers

Each `generate_...` function returns a grayscale image: bright cracks (230) on a dark background
(10). Where possible, a matching `..._ground_truth` or `..._topology` function gives the exact
expected answer from the same parameters. The image itself never carries its answer.

| Generator | Shape | Used to check |
|---|---|---|
| `generate_t_junction` | One T at a chosen angle | Junction angles and labels |
| `generate_curved_t_junction` | A T whose host is a circular arc | Angles on a curved host; curvature = 1/radius |
| `generate_y_junction` | Three arms at chosen directions | Y labels; any three-way shape |
| `generate_double_t_junction` | Two T's close together | Neighbouring junctions not interfering |
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

- **`validation_cases.py`** defines 12 cases:
  - 6 junction-classification cases
  - 1 corner cross-check
  - 2 curvature
  - 3 anisotropy
- Each case draws a synthetic image, runs the real pipeline, saves its overlay or rose plot, and
  builds an expected-vs-measured table.
- The pass/fail tolerances are copied from the matching tests, with a comment pointing to them.
- **Two cases show known weaknesses on purpose**:
  - the corner check on a sharply curved host
  - the anisotropy blind spot on an orthogonal grid
- **`validation_report.py`** turns the results into one HTML page.
- Run it with `python3 -m scripts.validation.validation_gallery`. A ready-made copy is in
  `examples/validation_gallery.html`.

Every row is a real check. The dominant direction in `anisotropy_aligned` must lie within 10° of
0° on the 0–180° circle, the same tolerance as `tests/test_anisotropy.py`.

## `scripts/validation/`

| Script | Kind | What it shows |
|---|---|---|
| `window_sweep.py` | Setting sweep | Picks the junction ring's outer radius (60 px) by testing 20–80 px on synthetic T's and choosing the smallest worst-case error. |
| `corner_window_sweep.py` | Setting sweep | Picks the corner wall length (10 px) the same way, also checking how often corners are found at all. |
| `curvature_window_sweep.py` | Setting sweep | Picks the curvature window (10 px) against arcs of known radius. |
| `junction_tolerance_sweep.py` | Sensitivity, real images | How much the T/Y counts move with the angle cut-offs. Results in `docs/junction_tolerance_sensitivity.md`. |
| `segmentation_sensitivity_sweep.py` | Sensitivity, real image | How much results move if the crack/not-crack threshold changes. |
| `skeleton_loop_sweep.py` | Measurement, real images | How common short junction-to-junction edges are, per image (mostly close junctions, not loops; see `docs/design_notes.md`). |
| `validation_gallery.py` | Gallery | The 12-case page above. |
| `crack_stats_synthetic_gallery.py` | Gallery | Synthetic grids and flakes through the crack-stats path, expected vs measured. |
| `synthetic_benchmark_raw_gallery.py`, `synthetic_benchmark_report.py` | Gallery | A 9-case benchmark: first the raw images with exact answers, then the measured results. |
| `pipeline_stage_figures.py` | Figures | Step-by-step panels from raw image to final graph, for a real image. |
| `render_area_method_viewer.py` | Figures | The four area methods (page 6) drawn side by side. |

The **sweeps** justify the 🟡 settings in `CALIBRATION.md`. The **sensitivity** checks don't pick
a value; they show how much a 🔴 setting matters.

## `tests/`

22 files, 174 tests (a few tests run several cases each). All pass. Each checks one module against synthetic cases with known
answers, or checks a fixed bug stays fixed.

| Test file | Tests | Covers |
|---|---|---|
| `test_junction_angle.py` | 12 | Junction angles and labels, incl. a loop back to its own junction (page 7) |
| `test_corners.py` | 8 | Corner cross-check, incl. west-pointing regression (page 8) |
| `test_precedence.py` | 7 | Precedence arrows, conflicts, cycles incl. self-arcs (page 9) |
| `test_edge_metrics.py` | 12 | Width, the four area bounds, and leaving flaking-cut edges out of totals (page 6) |
| `test_skeleton.py` | 7 | Pruning, the host-stub rule and dark-speck removal (page 2) |
| `test_curvature.py`, `test_anisotropy.py` | 7 + 7 | Page 10 |
| `test_grid_synthetic.py` | 9 | Topology on meshes, flaking on synthetic flakes (pages 3–4) |
| `test_export_crack_stats.py`, `test_export_crack_stats_v3.py` | 14 + 5 | Export helpers, incl. parallel segments in the network (page 5) |
| `test_entry_points.py` | 8 | Smoke tests: `analyze_image.py`, both `compute_row`s, the overview figure, `region.py` and the GUI each run end to end on a small synthetic flaked grid |
| `test_junction_tolerance_sweep.py` | 3 | The cut-off sweep's helpers |
| `test_synthetic*.py` | 1 + 21 + 11 | The generators, and the 9-case benchmark through the pipeline |
| `test_cache_io.py`, `test_html_report.py`, `test_xlsx_report.py`, `test_summary_plots.py`, `test_tiling.py`, `test_validation_*.py` | 2–8 each | Outputs (page 12) and the gallery |

The entry-point smoke tests (review finding 16) check that each entry point runs, not its
numbers; the library tests above cover those.

## `scripts/experimental/tracing_poc.py`

A throwaway proof of concept for a faster way to trace crack centre lines without
skeletonizing. It belongs to the in-situ drying-video idea in
`docs/experimental/dynamic_tracking_hypothetical.md`. It tests only three simple synthetic shapes
(a triangle, a rectangle and an L-shape), and is **not validated and not connected to the pipeline**.
