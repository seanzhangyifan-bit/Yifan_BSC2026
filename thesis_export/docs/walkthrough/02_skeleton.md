# 2. Skeletonizing

**File**: `src/crackgraph/skeleton.py` (~225 lines)

**What it does.** It thins every crack in the mask down to a line **1 pixel wide** running along
its middle, called the **skeleton**, then removes junk branches the thinning creates.

**Why.** Thick blobs can't be measured as a network. On 1-pixel lines, a crack's length is the
number of pixels it covers, and a junction is wherever 3 or more lines meet.

**The hard part is the cleanup.** Most of this file decides which branches are fake.

### What the library steps do

**Thinning** (`skeletonize`, scikit-image).

![Thinning, pass by pass](img/thinning.gif)

Each pass removes the edge pixels (orange) that can go without breaking a line or opening a hole,
like peeling an onion, until only a centre line 1 pixel wide is left (green).

`skeletonize()` doesn't show its intermediate passes, so the animation uses scikit-image's
`thin()`, a close relative, and then shows both finished results. They differ at the square
bulge on the left. `thin()` leaves no side branch there. `skeletonize()`, which the pipeline
uses, leaves two short stubs (circled, 2 and 4 px). Bumps on a crack wall turn into short dead
ends like these, and the pruning below removes them. (COMPARE LATER)

**Width map** (`distance_transform_edt`, SciPy).

![Distance transform](img/distance_transform.png)

Every crack pixel gets its distance to the nearest background pixel. On the centre line that
distance is about half the crack's width, so crack width ≈ 2 × value − 1. The bulge reads 6, the
horizontal crack 4 and the tapering stem 2–3.

**Branch types and pruning** (`skan.summarize`, `prune_paths`).

![skan branch types before and after pruning](img/skan_branch_types.png)

skan splits the skeleton into branches at the junctions and labels each one with a type. The
cleanup loop below removes only short type 0 and type 1 branches: here the short spur at the top
left and the tiny speck at the bottom left. Removing the spur also removes its junction, so the
two orange and blue pieces on the left merge into one longer dead end. That's why the loop runs
again after each removal. Note that the closed cell on the right counts as type 2, not 3: it is
made of junction-to-junction branches. Only a ring with no junction at all is type 3.

---

## Opening description, lines 1–15

A short summary of the above, plus the main known limitation. The pruning below never removes
**small loops** around dark specks inside wide cracks (thinning can't create a loop without a hole
in the mask, so these come from specks too big for the fill), or **short edges** between junctions
that sit close together. The full reasoning (measurements, rejected methods,
references) lives in [`docs/design_notes.md`](../design_notes.md).

## Settings, lines 26–45

| Line | Setting | Value | Meaning |
|---|---|---|---|
| 30 | `SPUR_PX_PLACEHOLDER` | 15 px = 9.1 µm | Dead ends and loose pieces shorter than this are removed. 🟢 About the largest measured agglomerate size and the typical film thickness, so shorter branches can't be told from wall roughness. See `docs/calibration_notes.md`. |
| 35 | `HOLE_AREA_THRESHOLD_PX2` | 50 px² | Holes inside a crack smaller than this are filled first, so the skeleton doesn't loop around a speck of dust. 🔴 |
| 41 | `CORR_THRESHOLD` | 0.99 | How steadily a branch's width must grow to count as a fake corner branch (see below). 🟡 Hand-tested at 0.8–0.99 on one image. |
| 45 | `MIN_LEN_FOR_CORR_PX` | 4 px | Branches shorter than this skip the width test; too few points to judge. 🔴 |

## Result containers, lines 48–77

- **`PrunedBranchRecord`** (line 49): one removed branch. It stores *why* it was removed
  (`"spur"`, `"fragment"` or `"corner_artifact"`), its length and its exact pixel path, so you
  can later draw what was cut.
- **`SkeletonResult`** (line 61): everything this step produces. The fields that matter most:
  - `skeleton`: the cleaned skeleton as a skan network. The next step uses this.
  - `mask_clean`: the crack mask after specks are removed and holes filled. Crack area is
    counted from this.
  - `medial_radius`: the **width map**. For every crack pixel, its distance to the nearest crack
    edge, which is half the local crack width. Every width number in the project comes from
    this.
  - The rest are counts and lengths of what was removed, for reporting.

---

## `_tip_ordered_width_profile(...)`, line 80

**For**: listing the crack width at each pixel along one branch, **starting from its loose end**,
so the next function can ask "does the width grow as you walk in from the tip?"

| Line | Code | What it means |
|---|---|---|
| 80–86 | header | Inputs: the skeleton, the width map, which branch (`path_index`), and its two endpoint IDs. Returns a list of widths. The leading `_` means "internal helper". |
| 92 | `coords = skel.path_coordinates(int(path_index))` | The branch's pixels in order, from its stored start point to its end point. |
| 93 | `if skel.degrees[int(node_id_dst)] == 1:` | Is the *end* point a loose end? (Degree 1 = only one branch touches it.) |
| 94 | `coords = coords[::-1]` | If so, flip the list so it starts at the tip. `[::-1]` = reversed. |
| 95 | `rr, cc = path_pixel_indices(coords, medial_radius.shape)` | Positions → whole-number pixel indices (rows, columns), clamped inside the image. Helper from `graph.py`. |
| 96 | `return 2.0 * medial_radius[rr, cc]` | Look up the half-width at every pixel at once, and double it. |

**Small blind spot.** For an isolated piece with two loose ends, line 94 always flips it, so the
direction is arbitrary. The next function only flags width that *rises*, so a piece ramping the
other way isn't caught. That rarely matters, since short isolated pieces are removed by length
anyway.

## `is_corner_tracing_artifact(widths, ...)`, line 99

**The idea.** Thinning sends a branch into every sharp inward corner of a crack's outline, even
where no crack exists. Along such a fake branch, the width climbs steadily toward the corner.
Along a real crack, the width wobbles around a constant value.

| Line | Code | What it means |
|---|---|---|
| 109–111 | `if n < min_len_px: return False` | Too short to judge → keep it. |
| 112–113 | `if widths.std() == 0: return False` | Perfectly constant width → not growing → keep it. (Also avoids dividing by zero.) |
| 114–115 | `corr = np.corrcoef(positions, widths)[0, 1]` | **The key line.** Correlation between "position along the branch" and "width": near 0 = flat (real), near +1 = steady growth (fake). |
| 116 | `return bool(corr > corr_threshold)` | Fake if above 0.99. |

Correlation tests for a *trend*. That's why it replaced an earlier "share of pixels wider than
the tip" test, which behaved like a coin flip on real noisy cracks. See `docs/design_notes.md`.

## `skeletonize_and_prune(mask, ...)`, line 119: the main function

**Preparation**

| Line | Code | What it means |
|---|---|---|
| 128 | `remove_small_objects(mask, min_size=min_object_px)` | Delete specks under 4 pixels. |
| 129 | `remove_small_holes(..., area_threshold=HOLE_AREA_THRESHOLD_PX2)` | Fill holes under 50 px² inside cracks. |
| 130 | `skel_image = skeletonize(mask_clean)` | **The thinning.** Zhang–Suen, via scikit-image. |
| 138 | `medial_radius = distance_transform_edt(mask_clean)` | The width map. On a full image this takes about 13 seconds, the slowest single step. |
| 140 | `skel = skan.Skeleton(skel_image, source_image=source_image)` | Hand the skeleton to skan, which turns pixels into branches and junctions. |

**The cleanup loop, line 148.** It repeats up to 10 times and stops early when a round removes
nothing.

| Line | Code | What it means |
|---|---|---|
| 149 | `summary = skan.summarize(skel, separator="_")` | A table with one row per branch: length (`branch_distance`) and **type**. Type 0 = isolated piece, 1 = dead end, 2 = junction to junction, 3 = closed loop. |
| 152 | `is_spur = (type == 1) & (length < spur_px)` | Short dead ends. |
| 153 | `is_fragment = (type == 0) & (length < spur_px)` | Short isolated pieces. |
| 164–177 | corner check | For dead ends and isolated pieces that *weren't* already too short, run the width-growth test on each. |
| 179–180 | `if ... == 0: break` | Nothing flagged → done. |
| 181–200 | record | Save each flagged branch's length and pixel path *before* removing it, because skan renumbers branches after every removal. |
| 203 | `skel = skel.prune_paths(...)` | **Remove all flagged branches.** skan returns a fresh, cleaned skeleton. |

**Why repeat?** Removing one spur can turn a junction into a plain bend, which can make a
neighbouring branch into a new short dead end. The next round catches it.

**Return, line 208.** Packs everything into `SkeletonResult`.

### What gets removed on real images

![Branches removed on real micrographs](img/real_pruned_branches.png)

Three examples of each removal reason, from 2048 × 2048 px centre crops of three micrographs,
chosen at the 25th, 50th and 95th length percentile of their group. "Width" is the crack width at
the branch's loose end → at its other end; "corr" is the number the corner test checks.

- **Spurs** (top row, orange): short dead ends. Most are stubs from the centre line to a bump or
  corner on the crack wall, like the middle and right examples. Some are the start of a real
  faint side crack whose rest fell below the Otsu cutoff, like the left example.
- **Fragments** (middle row, purple): short isolated pieces. These are mostly bits of real faint
  cracks that thresholding broke into dashes, not noise.
- **Corner branches** (bottom row, red): longer than 15 px, so the length rule misses them, but
  the width climbs steadily from the tip to the junction (here 4 → 28 px up to 6 → 42 px). The
  correlation is 0.99–1.00.

**The numbers** (same three crops, `spur_px` = 15):

| Image | Spurs | Fragments | Corner branches | Skeleton length removed |
|---|---|---|---|---|
| T3-PTFE_v1 (dense, wide cracks) | 162 | 44 | 48 | 5.4% |
| T4-M_H95_v1 (dense, membrane) | 66 | 6 | 13 | 1.9% |
| T5-PTFE_H95_v1 (sparse, thin cracks) | 39 | 130 | 0 | 6.9% |

| Reason | Count | Median length | Range |
|---|---|---|---|
| Spur | 267 | 9 px | 1–15 px |
| Fragment | 180 | 4 px | 1–15 px |
| Corner branch | 61 | 20 px | 15–44 px |

For corner branches, the width at the junction end is a median 7.6× the width at the tip, and
the median correlation is 0.996.

**What this means for the statistics.** On wide-crack images, most of what gets removed is
spurs and corner branches, which are artifacts. On thin-crack images such as T5-PTFE_H95, most is
fragments of real faint cracks. Removing them lowers total crack length (6.9% here) and the
component count `N`, because each fragment would otherwise count as its own component. So
fragment pruning is a choice about what counts as a crack, not just cleanup.

Not every corner branch is caught. Some with a correlation just under 0.99 survive as short dead
ends. A check on six crops found about 27 such misses, mostly on T3-PTFE and T4-M_H95, which
shorten the median edge length `ledge` by up to about 9% on those images.

These figures and numbers come from `scripts/docs/make_walkthrough_figures.py`. They skip the
flaking exclusion that the batch export applies, so they won't match the export exactly.

---

## Worth knowing

- **Only types 0 and 1 are ever removed.** Junction-to-junction branches (type 2) and loops
  (type 3) are never touched. `scripts/validation/skeleton_loop_sweep.py` finds 0–55% of edges
  per image are junction-to-junction edges shorter than the crack width. Only about 8% of those
  sit next to a dark speck (a real small loop); the rest are short segments between close
  junctions. See `docs/design_notes.md`.
- **Everything is in pixels.** Converting to µm happens in the exporter.
- **Tests**: `tests/test_skeleton.py` (8 tests):
  - width ramps are flagged; flat and noisy widths and short branches are not
  - a synthetic wedge is pruned only when the corner test is on
  - small holes are filled and large ones aren't Many other test files use `spur_px=3` instead of 15, so the default value
  itself isn't validated.
