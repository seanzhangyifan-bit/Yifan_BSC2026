# Calibration status of tunable constants

Every constant here is a fixed literal, not something computed from a formula (e.g.
`h/2`). Two, `SPUR_PX_PLACEHOLDER` and `DARK_SPECK_AREA_PX`, are 🟢: their values match
measured physical length scales (agglomerate size, film thickness) via the µm-per-px
calibration for `mm` images (0.6098 µm/px). Since 2026-11-13 the analysis stores them in µm
(`SPUR_UM` = 9.15 µm, `DARK_SPECK_AREA_UM2` = 48.3 µm² in `settings.py`) and converts them with the
µm per pixel the user sets; at 0.6098 µm/px they are exactly 15 px and 130 px.
`CURVATURE_WINDOW_PX_PLACEHOLDER` is 🟡.

* 🟢 **derived** — follows from geometry/math, not a guess
* 🟡 **empirical, uncalibrated** — justified by a synthetic sweep script, but standing in
for real µm-per-px/film-thickness calibration that doesn't exist yet
* 🔴 **assumed** — no sweep or derivation backing it yet

**Net, of the constants listed: 1 🟡, 2 🟢.** Not listed yet, and all 🔴 assumed: the flaking
constants (`WIDTH_FLAG_MULTIPLIER_K`, `MIN_CANDIDATE_AREA_PX`, `GROWTH_MULTIPLIER`,
`GROWTH_STEP_PX` in `flaking.py`, each set on one image) and the anisotropy window
(`ORIENT_WINDOW_PX_PLACEHOLDER`). So most of this project's tunables are still asserted, not
measured — a real, reportable state of the pipeline, not a documentation gap. The
code walkthrough (`docs/walkthrough/`) explains each constant's
rationale on the page for its module.

|Constant|File:Line|Value|Status|Reason|
|-|-|-|-|-|
|`CURVATURE_WINDOW_PX_PLACEHOLDER`|[`curvature.py:60`](src/crackgraph/curvature.py)|10.0|🟡 empirical, uncalibrated|minimax-RMSE sweep, `scripts/validation/curvature_window_sweep.py` (rationale in the comment under the constant)|
|`SPUR_PX_PLACEHOLDER`|[`skeleton.py:24`](src/crackgraph/skeleton.py)|15|🟢 derived (after the fact)|15 px = 9.1 µm ≈ largest measured agglomerates (d99 of inks T2–T4, 7–10 µm) and typical film thickness (8–16 µm); `mm` images only. Tests still override it (`spur_px=3`)|
|`DARK_SPECK_AREA_PX`|[`skeleton.py:30`](src/crackgraph/skeleton.py)|130|🟢 derived|130 px = 48 µm², the area of a d90 ≈ 7.8 µm agglomerate (inks T2–T4); `mm` images only. Was `HOLE_AREA_THRESHOLD_PX2` = 50 (🔴) until 2026-11-11|

## Not included here

Display-only constants (`MAX_PANEL_REGIONS` in `figures.py`, `SKELETON_DILATE_PX` in
`pipeline_figures.py`) are rendering choices, not
measurement calibration, so they don't belong in a table about calibration status.
