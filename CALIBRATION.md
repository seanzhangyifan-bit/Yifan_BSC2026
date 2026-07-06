# Calibration status of tunable constants

Every constant here is a fixed literal, not something computed from a formula (e.g.
`h/2`) — so none currently qualify as 🟢 *derived*. That tag is kept in the legend for
constants that may earn it later (once real film-thickness/µm-per-px calibration
exists), and to make explicit that the split below isn't a coincidence.

- 🟢 **derived** — follows from geometry/math, not a guess
- 🟡 **empirical, uncalibrated** — justified by a synthetic sweep script, but standing in
  for real µm-per-px/film-thickness calibration that doesn't exist yet
- 🔴 **assumed** — no sweep or derivation backing it yet

**Net: 2 🟡, 13 🔴, 0 🟢.** Most of this project's tunables are asserted, not measured —
that's a real, reportable state of the pipeline right now, not a documentation gap. See
[`docs/calibration_notes.md`](docs/calibration_notes.md) for each constant's full
rationale (relocated verbatim from its old inline comment).

| Constant | File:Line | Value | Status | Reason |
|---|---|---|---|---|
| `ANNULUS_INNER_PX_PLACEHOLDER` | [`junctions.py:77`](src/crackgraph/junctions.py) | 5.0 | 🔴 assumed | "a few px" heuristic; no sweep — both sweep scripts hold it fixed |
| `ANNULUS_OUTER_PX_PLACEHOLDER` | [`junctions.py:84`](src/crackgraph/junctions.py) | 60.0 | 🟡 empirical, uncalibrated | minimax-RMSE sweep, `scripts/window_sweep.py` |
| `QUAD_MIN_SPAN_PX` | [`junctions.py:108`](src/crackgraph/junctions.py) | 15.0 | 🔴 assumed | reasoned (needs "lever arm" for a stable quadratic) but no formula or sweep pins the exact value |
| `Y_ANGLE_TOL_DEG_PLACEHOLDER` | [`junctions.py:113`](src/crackgraph/junctions.py) | 15.0 | 🔴 assumed | no sweep, no noise model |
| `T_STRAIGHT_TOL_DEG_PLACEHOLDER` | [`junctions.py:119`](src/crackgraph/junctions.py) | 20.0 | 🔴 assumed | no sweep |
| `T_RIGHT_TOL_DEG_PLACEHOLDER` | [`junctions.py:123`](src/crackgraph/junctions.py) | 20.0 | 🔴 assumed | no sweep |
| `CORNER_SEARCH_RADIUS_PX` | [`corners.py:58`](src/crackgraph/corners.py) | 25.0 | 🔴 assumed | held fixed *in* the corner sweep, never itself swept |
| `CORNER_WINDOW_PX` | [`corners.py:64`](src/crackgraph/corners.py) | 10.0 | 🟡 empirical, uncalibrated | RMSE + unresolved-rate sweep, `scripts/corner_window_sweep.py` |
| `CORNER_MIN_TURN_DEG` | [`corners.py:77`](src/crackgraph/corners.py) | 45.0 | 🔴 assumed | held fixed in sweep script, never itself swept |
| `ABUTTER_AGREEMENT_TOL_DEG` | [`corners.py:82`](src/crackgraph/corners.py) | 30.0 | 🔴 assumed | no sweep |
| `BEARING_MATCH_TOL_DEG` | [`corners.py:88`](src/crackgraph/corners.py) | 30.0 | 🔴 assumed | no sweep |
| `SPUR_PX_PLACEHOLDER` | [`skeleton.py:22`](src/crackgraph/skeleton.py) | 15 | 🔴 assumed | heuristic tied to another unswept placeholder; tests override it (`spur_px=3`) rather than validate it |
| `KINK_WINDOW_PX_PLACEHOLDER` | [`kinks.py:27`](src/crackgraph/kinks.py) | 10.0 | 🔴 assumed | no sweep, unlike its annulus/corner-window cousins |
| `KINK_TURN_DEG_PLACEHOLDER` | [`kinks.py:32`](src/crackgraph/kinks.py) | 45.0 | 🔴 assumed | no sweep; correctness tests only, not calibration |
| `CORNER_TO_TANGENT_BEARING_TOL_DEG` | [`precedence.py:58`](src/crackgraph/precedence.py) | 45.0 | 🔴 assumed | comment self-documents as not yet swept |

## Not included here

Four constants in `overlay.py` — `TANGENT_TICK_LENGTH_PX`, `LABEL_OFFSET_VARIANTS_PX`,
`LABEL_NUDGE_DISTANCE_PX`, `PRECEDENCE_MIN_LINEWIDTH_PT` — are display/rendering choices,
not measurement calibration. Their own comments already disclaim any physical/geometric
meaning (e.g. "a display floor, not a claim about crack width"), so they don't belong in
a table about calibration status.
