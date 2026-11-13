# Validation and QA

Evidence that the analysis measures correctly and that its constants are justified. Not thesis
results. Constant status: `../../CALIBRATION.md`.

**Synthetic galleries** (known answers):
- `validation_gallery.py`: 5 cases (curvature, anisotropy) through the real pipeline, as one HTML
  page with expected-vs-measured tables.
- `crack_stats_synthetic_gallery.py`: synthetic grids and flakes through the crack-stats path.
- `synthetic_benchmark_raw_gallery.py`, `synthetic_benchmark_report.py`: a 9-case benchmark.
  First the raw images against closed-form answers, then the same cases through the pipeline at
  default settings. Degradation cases (illumination gradient, JPEG blocking, debris) report a
  measured change, since they have no exact answer.
- `pipeline_stage_figures.py <image>`: step-by-step figures (raw → mask → skeleton → graph) for
  one real image.

**Sweeps** (seeded, deterministic):
- `curvature_window_sweep.py`: picks the curvature window (minimax RMSE on arcs of known radius).
- `skeleton_loop_sweep.py`: share of short junction-to-junction segments per real image (0–55%);
  mostly close junctions, not loops (`docs/walkthrough/02_skeleton.md`).
- `segmentation_sensitivity_sweep.py`: how the threshold choice moves downstream stats.

**Tolerances** are copied, with a cross-reference, from the matching `tests/test_*.py`. Keep them
in sync by hand.
