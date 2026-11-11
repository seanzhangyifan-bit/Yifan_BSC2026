# 8. Corner cross-check

**File**: `src/crackgraph/corners.py` (~330 lines)

**What it does.** It measures each junction's angles a **second, completely different way**, then
reports whether it agrees with `junctions.py`.

**Why a second method.** The skeleton is least reliable exactly at junctions, where thick cracks
merge into a blob. This method ignores the skeleton. Instead it looks at the **intact film
tiles** between the cracks.

Where a crack meets another in a T, the abutter's width cuts a notch into the tile beside the
host. That splits the tile edge into two **sharp corners**, one on each side of the abutter.
Each corner's two walls point along the cracks there. A Y has three corners, one per tile.

It's a **cross-check, not a replacement**. Agreement is evidence the angle is right without
needing ground truth; disagreement gets logged, not smoothed over. It's still a straight-line
measurement over a short window, so a sharply curved host biases it too.

---

## Settings, lines 58–66

| Setting | Value | Meaning |
|---|---|---|
| `CORNER_SEARCH_RADIUS_PX` | 25 px | Look for corners this close to the junction. 🔴 |
| `CORNER_WINDOW_PX` | 10 px | Wall length used to measure each wall's direction. 🟡 Chosen by `scripts/validation/corner_window_sweep.py`. |
| `CORNER_MIN_TURN_DEG` | 45° | A wall must turn at least this sharply to count as a corner. 🔴 |
| `ABUTTER_AGREEMENT_TOL_DEG` | 30° | In a T, the two corners' readings of the abutter must agree within this. 🔴 |
| `BEARING_MATCH_TOL_DEG` | 30° | In a Y, walls shared by two corners must agree within this. 🔴 |

## Result containers, lines 69–87

- **`WallCorner`**: one corner: position, its two wall directions and how sharp it is.
- **`CornerCrossCheck`**: one junction:
  - the corners found
  - the three arm directions they imply
  - the gaps and the label
  - `agrees_with_tangent_fit`: does it match `junctions.py`'s label?
  - the biggest gap difference between the two methods
  - a reason if it couldn't decide

---

## `find_background_contours(mask_clean)`, line 90

The outlines of the tiles. `find_contours(~mask_clean, 0.5)` traces the boundary of everything
that *isn't* crack, as lists of (row, col) points.

## Angle helpers, lines 100–113

- `_bearing_deg`: direction of a vector, using the same convention as `junctions.py`.
- `_angle_diff(a, b)`: the shortest signed difference between two directions, wrapping round
  (179° vs −179° → 2°, not 358°).
- `_mean_bearing(a, b)`: the midpoint of two directions **the short way round**. This fixes the
  bug where 179° and −179° averaged to 0° (pointing the opposite way). See review finding 1 and
  the changelog.

## `_scan_contour_for_corners(...)`, line 116

It walks along one tile outline and finds sharp corners near the junction:

1. Skip the whole outline if it never comes within 25 px of the junction, or if it's too short.
2. At each point within 25 px: compare the wall direction over the previous 10 px with the
   direction over the next 10 px. If the turn is at least 45°, it's a candidate.
3. **Non-maximum suppression**: keep the sharpest candidates first, and drop any candidate
   within 20 px (2 × window) along the outline of one already kept, so one corner isn't counted
   several times.
4. For each kept corner, record both wall directions, each pointing *away* from the corner.

The outline is treated as having a start and an end, so a corner exactly at that seam would be
missed. That's a documented, rare edge case.

## `_pair_t_like(corners)`, line 186: exactly 2 corners → T-shaped

- Each corner has one wall along the host and one along the abutter. Which is which? The line
  joining the two corners runs along the host, so each corner's wall closest to that line is
  its host wall.
- The two corners' abutter walls should point the same way. If they differ by more than 30°,
  the junction is unresolved.
- Result: three arm directions: host side A, host side B, and the abutter (the wrap-safe
  average of the two readings).

## `_pair_y_like(corners)`, line 216: exactly 3 corners → Y-shaped

Each wall between two tiles is seen from both of its corners and points the same way from both.
So each of the 6 wall readings is matched to the closest reading from a *different* corner. Each
matched pair, averaged, gives one arm. If anything fails to match within 30°, it's unresolved.

## `_resolve_arm_bearings(corners)`, line 251

Dispatch on the **number** of corners: 2 → T-shaped pairing, 3 → Y-shaped, anything else →
unresolved. Corner *count* is a reliable signal because the topology fixes it. Corner *spacing*
isn't: at real crack widths, T and Y corners are similarly close together.

## `cross_check_junctions(...)`, line 266: the main function

For each junction from `junctions.py`:
1. Scan the tile outlines for corners near it. Outlines whose bounding box is farther away than
   the search radius are skipped up front; they couldn't contribute a corner anyway.
2. Turn the corners into three arm directions.
3. Compute the gaps and label them with the **same** `classify_from_gaps` as `junctions.py`, so
   any disagreement comes from the measurements, not from different rules.
4. Compare with `junctions.py`: same label? Biggest gap difference?

## Worth knowing

- **"Agrees" compares only the label and sorted gaps**, not *which arm* each method called the
  abutter. `precedence.py` does that arm-by-arm matching (page 9).
- **Tests**: `tests/test_corners.py` (8 tests) covers clean T, angled T, Y, ambiguous, curved
  host, too-short arms, and the west-pointing regression tests. The validation gallery shows the
  known weakness on a sharply curved host (radius 30 px).
