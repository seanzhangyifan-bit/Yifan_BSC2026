# 3. Flaking exclusion

**File**: `src/crackgraph/flaking.py` (~300 lines)

**The problem.** Some samples, mostly on membrane substrate, have patches where the catalyst
layer physically flaked off. The exposed substrate is bright, so Otsu marks it as "crack". But
it isn't a crack: it's missing material, and we have no idea what crack pattern was underneath.
Left in, it would inflate crack area and fill the skeleton with a fake branchy mesh.

**The approach**, in three steps:
1. **Find** patches far wider than this image's normal cracks. Width is the only test.
2. **Grow** each patch back out to its true edge and remove it from the mask.
3. **Flag** crack segments that run right next to the cut, because their lengths were shortened
   by *our* correction, not by the crack itself.

How this fits into the pipeline: skeletonize once (the "scout" pass) to get the width map, find
and remove flakes, then skeletonize **again** on the corrected mask. You'll see this two-pass
pattern in the exporter and in `analyze_image.py`.

---

## Settings, lines 27–61

Each setting has its comment *above* it.

| Line | Setting | Value | Meaning |
|---|---|---|---|
| 32 | `WIDTH_FLAG_MULTIPLIER_K` | 4.0 | A pixel is "suspiciously wide" if wider than 4 × this image's typical crack width. 🔴 |
| 36 | `MIN_CANDIDATE_AREA_PX2` | 500 px² | Ignore suspicious patches smaller than this; noise. 🔴 |
| 45 | `GROWTH_MULTIPLIER` | 2.2 | How far to grow a patch back out, in typical crack widths (explained below). 🟡 |
| 51 | `GROWTH_STEP_PX` | 3 px | Grow in 3-pixel steps. A speed setting, not a scientific choice. |
| 61 | `CUT_ADJACENT_BUFFER_WIDTH_MULTIPLIER` | 1.0 | Segments passing within 1 typical crack width of the cut are flagged. 🟡 |

**Why 2.2?** A pixel flagged at 4× width is, by construction, at least 2 widths from the patch's
edge, since the width map measures distance to the nearest edge. So the flagged area is the
patch shrunk inward by about 2 widths. Growing by 2.0 undoes that exactly; the extra 0.2 is a
safety margin checked by eye on one image.

## Result containers, lines 64–82

- **`FlakingCandidate`**: one suspicious patch: its label number, area, bounding box, and
  `solidity` (how compact it is). Solidity is recorded for information only; it used to be a
  second test but was dropped after it rejected a real elongated flake.
- **`FlakingResult`**: everything this step produces:
  - `reference_width_px`: this image's typical crack width.
  - `excluded_mask`: the pixels removed.
  - `mask_corrected`: the crack mask with those pixels removed.
  - The excluded area in pixels and as a percentage.

---

## `compute_reference_width_px(skel_image, medial_radius)`, line 84

This image's **typical crack width**: the median of (2 × half-width) over every skeleton pixel.

- **Why skeleton pixels only?** There, the width map reads a true half-width. Elsewhere it reads
  "how close this pixel is to an edge".
- **Why median?** A flake's own messy skeleton is a small share of all skeleton pixels, so it
  can't drag the median up the way it could drag a mean.

## `identify_candidates(...)`, line 95

| Line | What happens |
|---|---|
| 112 | `wide_mask = (2 × medial_radius > K × reference_width) & mask_clean`: mark every crack pixel wider than 4× typical. |
| 113 | `label(wide_mask)`: give each connected group of such pixels its own number. |
| 115–120 | Keep only groups of at least 500 px² as candidates. |

It returns the candidates *and* the numbered image, so the next step can find each candidate's
own pixels.

## `_grow_one_candidate(seed, local_mask, ...)`, line 123

Grow one patch outward step by step, never past real background:

- **Line 126**: the growth shape is a disk of radius 3 px.
- **Line 127**: the number of steps is the total growth distance divided by 3.
- **Line 130**: `binary_dilation(grown, ...) & local_mask` expands by one step, then cuts back to
  pixels that are still crack. The flake can only grow inside bright pixels.
- **Early stop**: if a step adds nothing, the patch has reached its edge.

It usually *doesn't* stop early. Flakes touch thin cracks, and growth creeps a little way down
them each step, so the 2.2× budget is a stopping rule, not a discovered boundary.

## `grow_and_exclude(...)`, line 137

Runs the growth for every candidate, each inside a cropped window around its bounding box (line
154: box + growth distance + 50 px), for speed. Growth is local, so cropping changes nothing.
The results are combined into one `excluded_mask`.

## `exclude_flaking_regions(mask_clean, skel_image, medial_radius)`, line 168: the main function

1. Typical width.
2. Find candidates.
3. If any were found, grow them; otherwise the excluded mask is empty.
4. **Line 199**: `mask_corrected = mask_clean & ~excluded_mask`, the crack mask with flakes
   removed.
5. Excluded area as pixels and as a % of the image.

If no candidates are found, `mask_corrected` equals `mask_clean`, and callers skip the second
skeletonize pass.

---

## Flagging segments near the cut

### `cut_adjacent_path_indices(...)`, line 213 (used by the v1 exporter)

It returns the segments whose path comes within 1 typical crack width of the excluded area **at
any point**, not just at their ends. The growth front is round, so it can graze along a crack's
side without cutting it. Checking only endpoints would miss that.

- **Line 258**: `distance_transform_edt(~excluded_mask) <= buffer_px` builds a "near the cut"
  zone in one fast step. This replaced a disk-growth method that gave identical results but took
  243 seconds instead of 7 on a full image.
- **Lines 260–264**: for each segment, look up its pixels in that zone. Any hit flags it.

Flagged segments are **dropped from length and width stats** but **kept in the connectivity
stats**. The segment is real; only its measured length is untrustworthy.

### `flake_touching_path_indices(...)`, line 269 (used by the v3 exporter)

v3's simpler rule: flag a segment if any of its pixels lies *inside* the excluded area. There's
no buffer, because v3 skeletonizes only once, on the uncorrected mask. The flake's own fake
mesh is still in the skeleton, and this removes it. v3 drops flagged segments from **everything**,
connectivity included. Page 5 compares v1 and v3.

---

## Worth knowing

- **Every setting was checked on one image** (T2-A_membran_v2). None were swept.
- **Tests**: `tests/test_grid_synthetic.py` runs a synthetic grid with stamped-on "flakes"
  (`generate_grid_with_flakes`). `tests/test_export_crack_stats_v3.py` covers
  `flake_touching_path_indices`.
- Full rationale, including the "reshape the boundary to look natural" idea that was rejected:
  [`docs/design_notes.md`](../design_notes.md).
