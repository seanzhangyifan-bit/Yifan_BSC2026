# Calibration status of tunable constants

Every constant here is a fixed literal, not something computed from a formula (e.g.
`h/2`). Two, `SPUR_PX_PLACEHOLDER` and `DARK_SPECK_AREA_PX`, are 🟢: their values match
measured physical length scales (agglomerate size, film thickness) via the µm-per-px
calibration for `mm` images (0.6098 µm/px). `CURVATURE_WINDOW_PX_PLACEHOLDER` is 🟡; the rest are 🔴.

* 🟢 **derived** — follows from geometry/math, not a guess
* 🟡 **empirical, uncalibrated** — justified by a synthetic sweep script, but standing in
for real µm-per-px/film-thickness calibration that doesn't exist yet
* 🔴 **assumed** — no sweep or derivation backing it yet

**Net: 1 🟡, 2 🔴, 2 🟢.** Most of this project's tunables are asserted, not measured —
that's a real, reportable state of the pipeline right now, not a documentation gap. See
[`docs/calibration_notes.md`](docs/calibration_notes.md) for each constant's full
rationale (relocated verbatim from its old inline comment).

|Constant|File:Line|Value|Status|Reason|
|-|-|-|-|-|
|`CURVATURE_WINDOW_PX_PLACEHOLDER`|[`curvature.py:60`](src/crackgraph/curvature.py)|10.0|🟡 empirical, uncalibrated|minimax-RMSE sweep, `scripts/validation/curvature_window_sweep.py` (rationale in the comment under the constant)|
|`SPUR_PX_PLACEHOLDER`|[`skeleton.py:24`](src/crackgraph/skeleton.py)|15|🟢 derived (after the fact)|15 px = 9.1 µm ≈ largest measured agglomerates (d99 of inks T2–T4, 7–10 µm) and typical film thickness (8–16 µm); `mm` images only. Tests still override it (`spur_px=3`)|
|`DARK_SPECK_AREA_PX`|[`skeleton.py:30`](src/crackgraph/skeleton.py)|130|🟢 derived|130 px = 48 µm², the area of a d90 ≈ 7.8 µm agglomerate (inks T2–T4); `mm` images only. Was `HOLE_AREA_THRESHOLD_PX2` = 50 (🔴) until 2026-11-11|
|`WIDTH_TRIM_INNER_PX_PLACEHOLDER`|[`edge_metrics.py`](src/crackgraph/edge_metrics.py)|5.0|🔴 assumed|"a few px" heuristic (or the local half-width if larger), no sweep|
|`AREA_JUNCTION_BLOB_RADIUS_PLACEHOLDER`|[`edge_metrics.py`](src/crackgraph/edge_metrics.py)|5.0|🔴 assumed|same heuristic again, no sweep|

## Not included here

Display-only constants (`THUMBNAIL_WIDTH_PX` in `xlsx_report.py`, `WHOLE_IMAGE_DISPLAY_MAX_DIM_PX`
in `summary_plots.py`, `SKELETON_DILATE_PX` in `pipeline_figures.py`) are rendering choices, not
measurement calibration, so they don't belong in a table about calibration status.
