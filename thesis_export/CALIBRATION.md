# Calibration status of tunable constants

Every constant here is a fixed literal, not something computed from a formula (e.g.
`h/2`) — so none currently qualify as 🟢 *derived*. That tag is kept in the legend for
constants that may earn it later (once real film-thickness/µm-per-px calibration
exists), and to make explicit that the split below isn't a coincidence.

* 🟢 **derived** — follows from geometry/math, not a guess
* 🟡 **empirical, uncalibrated** — justified by a synthetic sweep script, but standing in
for real µm-per-px/film-thickness calibration that doesn't exist yet
* 🔴 **assumed** — no sweep or derivation backing it yet

**Net: 3 🟡, 17 🔴, 0 🟢.** Most of this project's tunables are asserted, not measured —
that's a real, reportable state of the pipeline right now, not a documentation gap. See
[`docs/calibration\\\_notes.md`](docs/calibration_notes.md) for each constant's full
rationale (relocated verbatim from its old inline comment).

|Constant|File:Line|Value|Status|Reason|
|-|-|-|-|-|
|`ANNULUS\\\_INNER\\\_PX\\\_PLACEHOLDER`|[`junctions.py:77`](src/crackgraph/junctions.py)|5.0|🔴 assumed|"a few px" heuristic; no sweep — both sweep scripts hold it fixed|
|`ANNULUS\\\_OUTER\\\_PX\\\_PLACEHOLDER`|[`junctions.py:84`](src/crackgraph/junctions.py)|60.0|🟡 empirical, uncalibrated|minimax-RMSE sweep, `scripts/window\\\_sweep.py`|
|`QUAD\\\_MIN\\\_SPAN\\\_PX`|[`junctions.py:108`](src/crackgraph/junctions.py)|15.0|🔴 assumed|reasoned (needs "lever arm" for a stable quadratic) but no formula or sweep pins the exact value|
|`Y\\\_ANGLE\\\_TOL\\\_DEG\\\_PLACEHOLDER`|[`junctions.py:113`](src/crackgraph/junctions.py)|15.0|🔴 assumed|no sweep, no noise model|
|`T\\\_STRAIGHT\\\_TOL\\\_DEG\\\_PLACEHOLDER`|[`junctions.py:119`](src/crackgraph/junctions.py)|20.0|🔴 assumed|no sweep|
|`T\\\_RIGHT\\\_TOL\\\_DEG\\\_PLACEHOLDER`|[`junctions.py:123`](src/crackgraph/junctions.py)|20.0|🔴 assumed|no sweep|
|`CORNER\\\_SEARCH\\\_RADIUS\\\_PX`|[`corners.py:58`](src/crackgraph/corners.py)|25.0|🔴 assumed|held fixed *in* the corner sweep, never itself swept|
|`CORNER\\\_WINDOW\\\_PX`|[`corners.py:64`](src/crackgraph/corners.py)|10.0|🟡 empirical, uncalibrated|RMSE + unresolved-rate sweep, `scripts/corner\\\_window\\\_sweep.py`|
|`CORNER\\\_MIN\\\_TURN\\\_DEG`|[`corners.py:77`](src/crackgraph/corners.py)|45.0|🔴 assumed|held fixed in sweep script, never itself swept|
|`ABUTTER\\\_AGREEMENT\\\_TOL\\\_DEG`|[`corners.py:82`](src/crackgraph/corners.py)|30.0|🔴 assumed|no sweep|
|`BEARING\\\_MATCH\\\_TOL\\\_DEG`|[`corners.py:88`](src/crackgraph/corners.py)|30.0|🔴 assumed|no sweep|
|`SPUR\\\_PX\\\_PLACEHOLDER`|[`skeleton.py:22`](src/crackgraph/skeleton.py)|15|🔴 assumed|heuristic tied to another unswept placeholder; tests override it (`spur\\\_px=3`) rather than validate it|
|`HOLE\\\_AREA\\\_THRESHOLD\\\_PX2`|[`skeleton.py:91`](src/crackgraph/skeleton.py)|50|🔴 assumed|carried over unchanged from an earlier prototype comparison script; not independently derived or swept|
|`CORR\\\_THRESHOLD`|[`skeleton.py:63`](src/crackgraph/skeleton.py)|0.99|🟡 empirical, uncalibrated|4-point visual sweep (0.8/0.9/0.95/0.99) on one real image, T2-A\_membran\_v2|
|`MIN\\\_LEN\\\_FOR\\\_CORR\\\_PX`|[`skeleton.py:70`](src/crackgraph/skeleton.py)|4|🔴 assumed|no sweep; floor for a Pearson correlation to be meaningful at all|
|`KINK\\\_WINDOW\\\_PX\\\_PLACEHOLDER`|[`kinks.py:27`](src/crackgraph/kinks.py)|10.0|🔴 assumed|no sweep, unlike its annulus/corner-window cousins|
|`KINK\\\_TURN\\\_DEG\\\_PLACEHOLDER`|[`kinks.py:32`](src/crackgraph/kinks.py)|45.0|🔴 assumed|no sweep; correctness tests only, not calibration|
|`CORNER\\\_TO\\\_TANGENT\\\_BEARING\\\_TOL\\\_DEG`|[`precedence.py:58`](src/crackgraph/precedence.py)|45.0|🔴 assumed|comment self-documents as not yet swept|
|`WIDTH\\\_TRIM\\\_INNER\\\_PX\\\_PLACEHOLDER`|[`edge\\\_metrics.py`](src/crackgraph/edge_metrics.py)|5.0|🔴 assumed|same "a few px" heuristic as `ANNULUS\\\_INNER\\\_PX\\\_PLACEHOLDER`, no independent sweep|
|`AREA\\\_JUNCTION\\\_BLOB\\\_RADIUS\\\_PLACEHOLDER`|[`edge\\\_metrics.py`](src/crackgraph/edge_metrics.py)|5.0|🔴 assumed|same heuristic again, no sweep|

## Not included here

Four constants in `overlay.py` — `TANGENT\\\_TICK\\\_LENGTH\\\_PX`, `LABEL\\\_OFFSET\\\_VARIANTS\\\_PX`,
`LABEL\\\_NUDGE\\\_DISTANCE\\\_PX`, `PRECEDENCE\\\_MIN\\\_LINEWIDTH\\\_PT` — are display/rendering choices,
not measurement calibration. Their own comments already disclaim any physical/geometric
meaning (e.g. "a display floor, not a claim about crack width"), so they don't belong in
a table about calibration status.

