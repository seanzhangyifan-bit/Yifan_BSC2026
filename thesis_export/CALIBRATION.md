# Calibration status of tunable constants

Every constant here is a fixed literal, not something computed from a formula (e.g.
`h/2`) — so none currently qualify as 🟢 *derived*. That tag is kept in the legend for
constants that may earn it later (once real film-thickness/µm-per-px calibration
exists), and to make explicit that the split below isn't a coincidence.

* 🟢 **derived** — follows from geometry/math, not a guess
* 🟡 **empirical, uncalibrated** — justified by a synthetic sweep script, but standing in
for real µm-per-px/film-thickness calibration that doesn't exist yet
* 🔴 **assumed** — no sweep or derivation backing it yet

**Net: 3 🟡, 15 🔴, 0 🟢.** Most of this project's tunables are asserted, not measured —
that's a real, reportable state of the pipeline right now, not a documentation gap. See
[`docs/calibration_notes.md`](docs/calibration_notes.md) for each constant's full
rationale (relocated verbatim from its old inline comment).

|Constant|File:Line|Value|Status|Reason|
|-|-|-|-|-|
|`ANNULUS_INNER_PX_PLACEHOLDER`|[`junctions.py:77`](src/crackgraph/junctions.py)|5.0|🔴 assumed|"a few px" heuristic; no sweep — both sweep scripts hold it fixed|
|`ANNULUS_OUTER_PX_PLACEHOLDER`|[`junctions.py:79`](src/crackgraph/junctions.py)|60.0|🟡 empirical, uncalibrated|minimax-RMSE sweep, `scripts/validation/window_sweep.py`|
|`QUAD_MIN_SPAN_PX`|[`junctions.py:81`](src/crackgraph/junctions.py)|15.0|🔴 assumed|reasoned (needs "lever arm" for a stable quadratic) but no formula or sweep pins the exact value|
|`Y_ANGLE_TOL_DEG_PLACEHOLDER`|[`junctions.py:83`](src/crackgraph/junctions.py)|15.0|🔴 assumed|no noise model; sensitivity measured, not calibrated: see `docs/junction_tolerance_sensitivity.md` (Y count swings 6–208 across 5–25°)|
|`T_STRAIGHT_TOL_DEG_PLACEHOLDER`|[`junctions.py:85`](src/crackgraph/junctions.py)|20.0|🔴 assumed|sensitivity measured, not calibrated: see `docs/junction_tolerance_sensitivity.md`|
|`T_RIGHT_TOL_DEG_PLACEHOLDER`|[`junctions.py:87`](src/crackgraph/junctions.py)|20.0|🔴 assumed|sensitivity measured, not calibrated: see `docs/junction_tolerance_sensitivity.md`|
|`CORNER_SEARCH_RADIUS_PX`|[`corners.py:58`](src/crackgraph/corners.py)|25.0|🔴 assumed|held fixed *in* the corner sweep, never itself swept|
|`CORNER_WINDOW_PX`|[`corners.py:60`](src/crackgraph/corners.py)|10.0|🟡 empirical, uncalibrated|RMSE + unresolved-rate sweep, `scripts/validation/corner_window_sweep.py`|
|`CORNER_MIN_TURN_DEG`|[`corners.py:62`](src/crackgraph/corners.py)|45.0|🔴 assumed|held fixed in sweep script, never itself swept|
|`ABUTTER_AGREEMENT_TOL_DEG`|[`corners.py:64`](src/crackgraph/corners.py)|30.0|🔴 assumed|no sweep|
|`BEARING_MATCH_TOL_DEG`|[`corners.py:66`](src/crackgraph/corners.py)|30.0|🔴 assumed|no sweep|
|`SPUR_PX_PLACEHOLDER`|[`skeleton.py:30`](src/crackgraph/skeleton.py)|15|🔴 assumed|heuristic tied to another unswept placeholder; tests override it (`spur_px=3`) rather than validate it|
|`HOLE_AREA_THRESHOLD_PX2`|[`skeleton.py:35`](src/crackgraph/skeleton.py)|50|🔴 assumed|carried over unchanged from an earlier prototype comparison script; not independently derived or swept|
|`CORR_THRESHOLD`|[`skeleton.py:41`](src/crackgraph/skeleton.py)|0.99|🟡 empirical, uncalibrated|4-point visual sweep (0.8/0.9/0.95/0.99) on one real image, T2-A\_membran\_v2|
|`MIN_LEN_FOR_CORR_PX`|[`skeleton.py:45`](src/crackgraph/skeleton.py)|4|🔴 assumed|no sweep; floor for a Pearson correlation to be meaningful at all|
|`CORNER_TO_TANGENT_BEARING_TOL_DEG`|[`precedence.py:59`](src/crackgraph/precedence.py)|45.0|🔴 assumed|comment self-documents as not yet swept|
|`WIDTH_TRIM_INNER_PX_PLACEHOLDER`|[`edge_metrics.py`](src/crackgraph/edge_metrics.py)|5.0|🔴 assumed|same "a few px" heuristic as `ANNULUS_INNER_PX_PLACEHOLDER`, no independent sweep|
|`AREA_JUNCTION_BLOB_RADIUS_PLACEHOLDER`|[`edge_metrics.py`](src/crackgraph/edge_metrics.py)|5.0|🔴 assumed|same heuristic again, no sweep|

## Not included here

Four constants in `overlay.py` — `TANGENT_TICK_LENGTH_PX`, `LABEL_OFFSET_VARIANTS_PX`,
`LABEL_NUDGE_DISTANCE_PX`, `PRECEDENCE_MIN_LINEWIDTH_PT` — are display/rendering choices,
not measurement calibration. Their own comments already disclaim any physical/geometric
meaning (e.g. "a display floor, not a claim about crack width"), so they don't belong in
a table about calibration status.

