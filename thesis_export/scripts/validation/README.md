# Methodology validation & QA

**Purpose**: this tier's job is to *back the per-image pipeline's claims*, not to produce a thesis
result of its own. It answers "why this constant, not another" and "does the method recover a
known right answer" with actual numbers, not eyeballing. See `../../CALIBRATION.md` for the
status of every tunable constant this tier justifies.

**Synthetic ground-truth galleries** (known right answer, human-reviewable + numeric):
- `validation_gallery.py [--out-dir outputs/validation]`: 14 synthetic cases across all 5
  measurement methods, run through the real pipeline, compiled into one browsable HTML page with
  expected-vs-measured tables. Includes two cases that show a known method limitation honestly
  (severely curved host defeats the corner cross-check; an orthogonal grid reads as isotropic
  under the 2nd-order orientation tensor) rather than hiding them.
- `crack_stats_synthetic_gallery.py`, `synthetic_benchmark_raw_gallery.py`,
  `synthetic_benchmark_report.py`: a newer, larger 9-case synthetic-benchmark matrix (canonical
  geometries, structural networks, degradation resilience), built in two steps — raw geometry
  against closed-form ground truth first, then the same cases run through the real pipeline
  (`binarize` → `skeletonize_and_prune` → `extract_graph`) at production defaults. Degradation
  cases (illumination gradient, JPEG blocking, debris) report a measured delta, not a fabricated
  ground truth, since degraded output has none.
- `pipeline_stage_figures.py <image_path>`: per-stage walkthrough figures (raw → mask → cleaned →
  skeleton → final graph) for one real image, useful for explaining the pipeline visually.

**Calibration sweeps** (deterministic, seeded — justify a specific constant's value):
- `window_sweep.py`, `corner_window_sweep.py`, `curvature_window_sweep.py`: generate synthetic
  junctions with known geometry and seeded pixel jitter, sweep a window-size parameter, report
  bias/std/RMSE per (geometry, jitter, window) combination. The shipped defaults are the
  minimax-RMSE choice from these sweeps, not an eyeballed guess.
- `skeleton_loop_sweep.py`: audits every image in the real dataset for the spurious
  double-line-skeleton-loop artifact (0-55% of edges affected, image-dependent).
- `segmentation_sensitivity_sweep.py`: checks how binarization threshold choice moves downstream
  stats.
- `render_area_method_viewer.py`: interactive comparison of four cross-checked ways to compute
  per-edge crack area.

**Validation status**: every PASS/FAIL tolerance used here is *duplicated* (with a
cross-reference comment), never imported, from the matching `tests/test_*.py` constant — tests
aren't a dependency of `src/`. Keep them in sync by hand if a test's tolerance changes.
