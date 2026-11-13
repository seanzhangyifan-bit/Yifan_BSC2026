# 11. Validation and tests

A micrograph has no answer key, so the project draws **synthetic images** with known lengths,
directions and counts. Real images are used for **sensitivity**: how much results move when a
setting changes.

| Where | What |
|---|---|
| `src/crackgraph/synthetic.py` | Synthetic crack patterns with known answers |
| `src/crackgraph/synthetic_degradation.py` | Messier versions: uneven lighting, JPEG artefacts, debris |
| `src/crackgraph/validation_cases.py`, `validation_report.py` | The 5-case validation gallery |
| `scripts/validation/` | Galleries, setting sweeps, sensitivity checks |
| `tests/` | 99 automatic checks: `python3 -m pytest tests/` |

---

## `synthetic.py`

Each `generate_...` returns a grayscale image: cracks at 230 on a background of 10. Where
possible, a `..._ground_truth` or `..._topology` function gives the exact answer from the same
parameters.

| Generator | Shape | Checks |
|---|---|---|
| `generate_t_junction`, `generate_y_junction` | Three arms meeting | Three-way junctions; curvature of straight arms |
| `generate_curved_t_junction` | Stem meeting a circular arc | Curvature = 1/radius |
| `generate_double_t_junction` | Two close T shapes | Neighbouring junctions |
| `generate_straight_line`, `generate_kinked_line` | One line, straight or bent once | Curvature, tortuosity |
| `generate_oriented_segment_field` | Separate segments with set directions | Rose plot |
| `generate_grid`, `generate_wavy_grid`, `generate_hexagonal_grid` | Meshes with known node and segment counts | Topology, total length |
| `generate_grid_with_flakes` | A grid with filled circles | Flaking |
| `generate_tapered_line` | A crack thinning at both ends | Width and area at tips |
| `generate_converging_lines` | Two lines merging | Smallest separable gap |
| `generate_hierarchical_network` | Brick-pattern cracks plus secondary T's | A realistic known network |
| `generate_crescent_scale_pattern` | Overlapping crescents | Area and perimeter |
| `generate_density_gradient_field` | Segments denser left to right | Density across zones |

`jitter_px` adds edge wobble with a fixed seed, so runs are repeatable.

## `synthetic_degradation.py`

| Function | Simulates |
|---|---|
| `apply_illumination_gradient` | Uneven lighting |
| `apply_jpeg_blocking` | A low-quality JPEG save |
| `apply_debris` | Dark specks interrupting cracks |

No exact answer, so results are clean-vs-degraded differences. None of these effects has been
seen in the real images; they're precautionary (`[speculated]`).

## The validation gallery

- `validation_cases.py`: 5 cases, 2 curvature and 3 anisotropy. Each draws an image, runs the real
  pipeline, saves its overlay or rose plot and builds an expected-vs-measured table.
- Tolerances are copied from the matching tests, with a pointer.
- `anisotropy_orthogonal_grid` shows why the rose plot is reported rather than a single index.
- `validation_report.py`: one HTML page. Run `python3 -m scripts.validation.validation_gallery`;
  a copy is in `examples/validation_gallery.html`.

## `scripts/validation/`

| Script | Kind | Shows |
|---|---|---|
| `curvature_window_sweep.py` | Sweep | Picks the curvature window (10 px) on arcs of known radius. |
| `segmentation_sensitivity_sweep.py` | Sensitivity, real image | How results move with the threshold. |
| `skeleton_loop_sweep.py` | Real images | Share of short junction-to-junction segments (mostly close junctions, not loops; page 2). |
| `validation_gallery.py` | Gallery | The 5 cases above. |
| `crack_stats_synthetic_gallery.py` | Gallery | Synthetic grids and flakes through the crack stats. |
| `synthetic_benchmark_raw_gallery.py`, `synthetic_benchmark_report.py` | Gallery | 9-case benchmark: raw images with exact answers, then measured results. |
| `pipeline_stage_figures.py` | Figures | Step-by-step panels for one real image. |

Sweeps justify 🟡 settings; sensitivity checks show how much a 🔴 setting matters
(`CALIBRATION.md`).

## `tests/`

14 files, 99 tests, all passing. Run from `thesis_export/`.

| Test file | Tests | Covers |
|---|---|---|
| `test_skeleton.py` | 7 | Pruning, host stubs, dark specks (page 2) |
| `test_grid_synthetic.py` | 9 | Topology on meshes, synthetic flakes (pages 3–4) |
| `test_flaking_omission.py` | 5 | Leaving out flake-touching segments (page 3) |
| `test_unified_analysis.py` | 8 | Settings, regions, whole-image row vs the old exporter (pages 5–7) |
| `test_crack_stats_measure.py` | 9 | Crack-stats helpers, per-region counting (page 7) |
| `test_curvature.py`, `test_anisotropy.py` | 7 + 5 | Page 8 |
| `test_entry_points.py` | 3 | Command line and GUI run end to end (page 10) |
| `test_summary_plots.py` | 4 | Rose and histogram drawing (page 9) |
| `test_synthetic*.py` | 1 + 21 + 11 | Generators and the 9-case benchmark |
| `test_validation_*.py` | 3 + 6 | The validation gallery |

- `tests/fixtures/old_exporter_flaked_grid.json`: the old exporter's output on the synthetic
  flaked grid, frozen when it was archived.
- The entry-point tests check that things run, not their numbers; the other tests cover numbers.
