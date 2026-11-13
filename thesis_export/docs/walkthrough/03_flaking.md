# 3. Flaking exclusion

**File**: `src/crackgraph/flaking.py` (~240 lines)

**The problem.** Some samples have patches where the catalyst
layer physically flaked off. The exposed substrate is bright, so Otsu marks it as "crack". But
it isn't a crack: it's missing material, and we have no idea what crack pattern was underneath.
Left in, it would inflate crack area and fill the skeleton with a fake branchy mesh.

**The approach**, in three steps:
1. **Find** patches far wider than this image's normal cracks. 
2. **Grow** each patch back out.
3. **Omit** every skeleton segment that has a pixel inside a flaked patch, from the stats and
   from the connectivity graph.

How this fits into the pipeline: the mask is skeletonized **once**, flaked patches included.
That skeleton's width map is used to find the patches, and the segments running into them are
then omitted. Crack area is the cleaned mask minus the patches.

---

## Settings, lines 27–49

Each setting has its comment *above* it.

| Line | Setting | Value | Meaning |
|---|---|---|---|
| 31 | `WIDTH_FLAG_MULTIPLIER_K` | 4.0 | A pixel is "suspiciously wide" if wider than 4 × this image's typical crack width. 🔴 |
| 35 | `MIN_CANDIDATE_AREA_PX` | 500 px | Ignore suspicious patches smaller than this; noise. 🔴 |
| 43 | `GROWTH_MULTIPLIER` | 2.2 | How far to grow a patch back out, in typical crack widths (explained below). 🟡 |
| 49 | `GROWTH_STEP_PX` | 3 px | Grow in 3-pixel steps. A speed setting, not a scientific choice. |

**Why 2.2?** A pixel flagged at 4× the typical crack width is, by construction, at least 2 full crack widths from the patch's
edge, since the width map measures distance to the nearest edge. So the flagged area is the
patch shrunk inward by about 2 widths. Growing by 2.0 undoes that exactly; the extra 0.2 is a
safety margin checked by eye on one image.

## Result containers, lines 51–68

- **`FlakingCandidate`**: one suspicious patch: its label number, area, bounding box, and
  `solidity` (how compact it is). Solidity is recorded for information only.
- **`FlakingResult`**: everything this step produces:
  - `reference_width_px`: this image's typical crack width.
  - `excluded_mask`: the flaked pixels.
  - `mask_corrected`: the crack mask without them. Crack area is counted from this.
  - The excluded area in pixels and as a percentage.

---

## `compute_reference_width_px(skel_image, medial_radius)`, line 71

This image's **typical crack width**: the median of (2 × half-width) over every skeleton pixel.

- **Why skeleton pixels only?** There, the width map reads a true half-width. Elsewhere it reads
  "how close this pixel is to an edge".
- **Why median?** A flake's own messy skeleton is a small share of all skeleton pixels, so it
  can't drag the median up the way it could drag a mean.

## `identify_candidates(...)`, line 82

| Line | What happens |
|---|---|
| 99 | `wide_mask = (2 × medial_radius > K × reference_width) & mask_clean`: mark every crack pixel wider than 4× typical. |
| 100 | `label(wide_mask)`: give each connected group of such pixels its own number. |
| 102–106 | Keep only groups of at least 500 px as candidates. |

It returns the candidates *and* the numbered image, so the next step can find each candidate's
own pixels.

## `_grow_one_candidate(seed, local_mask, ...)`, line 110

Grow one patch outward step by step, never past real background:

- **Line 113**: the growth shape is a disk of radius 3 px.
- **Line 114**: the number of steps is the total growth distance divided by 3.
- **Line 117**: `binary_dilation(grown, ...) & local_mask` expands by one step, then cuts back to
  pixels that are still crack. The flake can only grow inside bright pixels.
- **Early stop**: if a step adds nothing, the patch has reached its edge.

It usually *doesn't* stop early. Flakes touch thin cracks, and growth creeps a little way down
them each step, so the 2.2× budget is a stopping rule, not a discovered boundary.

## `grow_and_exclude(...)`, line 124

Runs the growth for every candidate, each inside a cropped window around its bounding box (line
141: box + growth distance + 50 px), for speed. Growth is local, so cropping changes nothing.
The results are combined into one `excluded_mask`.

## `exclude_flaking_regions(mask_clean, skel_image, medial_radius)`, line 155: the main function

1. Typical width.
2. Find candidates.
3. If any were found, grow them; otherwise the excluded mask is empty.
4. **Line 186**: `mask_corrected = mask_clean & ~excluded_mask`, the crack mask with flakes
   removed.
5. Excluded area as pixels and as a % of the image.

If no candidates are found, `mask_corrected` equals `mask_clean` and nothing is omitted.

---

## Omitting segments that touch a flake

### `flake_touching_path_indices(...)`, line 200

Flag a segment if **any** of its pixels lies inside the excluded area (lines 217–221). There's no
buffer around the flake: the skeleton was built once, from the uncorrected mask, so the flake's
own fake mesh is exactly the skeleton inside the excluded area.

Flagged segments are left out of the length and width stats
*and* the connectivity graph. 

### `remove_flake_touching_edges(...)`, line 226

For tools that analyse the graph itself (curvature, anisotropy, per-segment metrics) rather than only
summing stats over it: removes the flagged segments from the skeleton and rebuilds the graph.
Where a three way junction loses a branch, its two remaining segments merge into one. `analyze_image.py`
and the overview figure use this.

---

## Worth knowing

- **Every setting was checked on one image** (T2-A_membran_v2). No hyperparameters were swept over multiple values.
- **Tests**: `tests/test_grid_synthetic.py` runs a synthetic grid with stamped-on "flakes"
  (`generate_grid_with_flakes`). `tests/test_flaking_omission.py` covers
  `flake_touching_path_indices` and `remove_flake_touching_edges`.
