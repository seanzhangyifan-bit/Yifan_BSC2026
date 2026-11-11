# 7. Junction classification

**File**: `src/crackgraph/junctions.py` (476 lines)

**What it does.** At every three-way junction, it measures the directions of the three arms and
labels the junction:

- **T**: two arms form a straight line (about 180° apart) and the third meets them at about 90°.
  The third crack, the **abutter**, ran into an existing crack, the **host**, and stopped. So
  *the host is older*. That one local fact is what the ordering analysis is built on.
- **Y**: three arms about 120° apart. All three probably formed together, so there's no ordering
  information.
- **ambiguous**: neither pattern fits closely enough. No claim is made.
- **insufficient_data**: an arm was too short to measure.

Only degree-3 junctions are labelled. Crossings of 4 or more are counted but never split up
into guessed pairs.

---

## The opening description, lines 1–67: why it's done this way

It's long, but it explains three hard-won choices:

1. **Measure in a ring (annulus), not at the junction point and not along the whole arm.** Right
   at the junction, thinning makes the skeleton wobble. Far out, the crack may curve away. So
   each arm's direction is measured only from its pixels between 5 and 60 px from the junction.
2. **Fit a curve, not a straight chord.** A chord from the junction to the middle of a curved
   arm points off to one side. A curved host crack would then read as about 150° instead of
   180°, and a real T would become "ambiguous". So the ring pixels are fitted with a parabola,
   and its slope *at the junction* gives the direction. The curvature falls out of the same fit
   for free.
3. **Use sector gaps, not pairwise angles.** Sort the three directions around the circle and
   take the three gaps between neighbours. They always add up to exactly 360°. Plain pairwise
   angles fold anything over 180° back down and lose information.

## Settings, lines 77–87

| Setting | Value | Meaning |
|---|---|---|
| `ANNULUS_INNER_PX_PLACEHOLDER` | 5 px | Inner edge of the measuring ring. 🔴 |
| `ANNULUS_OUTER_PX_PLACEHOLDER` | 60 px | Outer edge. 🟡 Chosen by `scripts/validation/window_sweep.py`. |
| `QUAD_MIN_SPAN_PX` | 15 px | Arms with less than this inside the ring get a straight-line fit instead of a parabola. 🔴 |
| `Y_ANGLE_TOL_DEG_PLACEHOLDER` | ±15° | Every gap within this of 120° → Y. 🔴 |
| `T_STRAIGHT_TOL_DEG_PLACEHOLDER` | ±20° | Largest gap within this of 180° … 🔴 |
| `T_RIGHT_TOL_DEG_PLACEHOLDER` | ±20° | … and the other two within this of 90° → T. 🔴 |

The last three decide the junction census. How much the counts depend on them is measured in
[`docs/junction_tolerance_sensitivity.md`](../junction_tolerance_sensitivity.md): absolute
counts depend a lot, comparisons between conditions much less.

## Result containers, lines 90–134

- **`EdgeDirection`**: one arm's measurement:
  - `bearing_deg`: its direction.
  - `curvature_per_px`: how sharply it curves.
  - `fit_degree`: 2 = parabola, 1 = straight line, 0 = fallback.
  - `fit_rms_px`: how well the fit matched.
  - The fitted curve itself, so it can be drawn.
- **`JunctionClassification`**: one junction:
  - its three arms
  - its three gaps
  - its label
  - for a T, which segment is the abutter and which two are the hosts
- **`JunctionAnalysisResult`**: all junctions plus the counts per label.

---

## `_build_incidence_index(summary)`, line 137

For each node, it lists which segments touch it and at which end. A segment that loops back to
the same node appears twice, once per end.

## `_edge_direction(...)`, line 152: measure one arm

| Lines | What happens |
|---|---|
| 159–162 | Get the arm's pixels, ordered *outward* from the junction. |
| 163–164 | Pick the pixels whose straight-line distance from the junction is between the inner and outer ring radius. |
| 169–190 | No pixels in the ring → fail with a reason. |
| 196–199 | `s`: distance *along* the arm from the junction, used as the fitting variable. |
| 213–229 | **Enough points and span → parabola.** Fit row(s) and column(s) as parabolas in `s`. The slope at `s = 0` is the arm's direction at the junction. The second derivative gives the signed curvature. |
| 230–240 | **Fewer points → straight line.** Direction only, no curvature. |
| 241–246 | **One point → a straight chord** from the junction to it. |
| 248–283 | Turn the direction into a unit vector and a bearing, and return. |

The fit is deliberately **not forced through the junction pixel**. That pixel sits inside the
blob and is slightly off-centre, and forcing through it skewed every direction.

## `_bearing_deg`, `sector_gaps_deg_from_bearings`, lines 286–316

- **Bearing**: `atan2(−drow, dcol)` in degrees. 0° = right, 90° = up.
- **Sector gaps**: sort the three bearings around the circle and return each neighbouring pair's
  gap, wrapping round, plus which arms bound it. They always sum to 360°.

## `classify_from_gaps(gaps, y_tol, t_straight_tol, t_right_tol)`, line 319

| Lines | Rule |
|---|---|
| 332–333 | All three gaps within `y_tol` of 120° → **Y**. Checked first, so Y wins if loose cut-offs ever let both match. |
| 338–344 | Take the largest gap. If it's within `t_straight_tol` of 180°, the two arms around it are the **hosts** and the third arm is the **abutter**. If both host–abutter gaps are within `t_right_tol` of 90° → **T**. |
| 346 | Otherwise → **ambiguous**. |

This function is shared with `corners.py` and `precedence.py`, so every method labels junctions
with the identical rule.

## `classify_junctions(...)`, line 349: the main function

For each degree-3 node:
1. **Lines 392–398**: if the width map is supplied, widen the inner ring radius to the local
   half-width. On thick cracks, the junction blob can be wider than 5 px.
2. **Lines 400–415**: not exactly 3 arms → `insufficient_data`.
3. **Lines 417–436**: measure each arm. If any fails → `insufficient_data`, with the reasons.
4. **Lines 438–461**: compute the gaps, classify, and record the abutter and hosts for a T.

Then it counts each label.

---

## Worth knowing

- **About two-thirds of real junctions come out "ambiguous"**, with angles between a T and a Y.
  See the sensitivity write-up.
- **The arm directions are labelled `[measured]`, but they're extrapolated from a fit.**
  `[interpreted]` would be more accurate (review finding 12).
- **The ring is picked by straight-line distance**, which mixes up both ends of a loop that
  comes back to its own junction. That never happened on two real images tested (review finding
  13).
- **Tests**: `tests/test_junction_angle.py` (11 tests): straight, angled, curved and noisy
  synthetic T's and Y's with known angles.
