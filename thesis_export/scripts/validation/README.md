# Methodology validation & QA

**Purpose**: this tier's job is to *back the per-image pipeline's claims*, not to produce a thesis
result of its own. It answers "why this constant, not another" and "does the method recover a
known right answer" with actual numbers, not eyeballing. See `../../CALIBRATION.md` for the
status of every tunable constant this tier justifies.

**Synthetic ground-truth galleries** (known right answer, human-reviewable + numeric):
- `validation_gallery.py [--out-dir outputs/validation]`: 5 synthetic cases across 2
  measurement methods (curvature/tortuosity, anisotropy), run through the real pipeline, compiled
  into one browsable HTML page with expected-vs-measured tables. Includes one case that shows a
  known method limitation honestly (an orthogonal grid reads as isotropic under the 2nd-order
  orientation tensor) rather than hiding it.
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
- `curvature_window_sweep.py`: generates synthetic shapes with known curvature and seeded pixel
  jitter, sweeps the curvature window, and reports bias/std/RMSE per (geometry, jitter, window)
  combination. The shipped default is the minimax-RMSE choice from this sweep, not an eyeballed
  guess.
- `skeleton_loop_sweep.py`: audits every image in the real dataset for short
  junction-to-junction edges (0-55% of edges, image-dependent). Originally framed as a
  doubled-line loop artifact; most turn out to be short segments between close junctions
  (see `docs/walkthrough/02_skeleton.md`).
- `segmentation_sensitivity_sweep.py`: checks how binarization threshold choice moves downstream
  stats.
- `render_area_method_viewer.py`: interactive comparison of four cross-checked ways to compute
  per-edge crack area.

**Validation status**: every PASS/FAIL tolerance used here is *duplicated* (with a
cross-reference comment), never imported, from the matching `tests/test_*.py` constant — tests
aren't a dependency of `src/`. Keep them in sync by hand if a test's tolerance changes.
