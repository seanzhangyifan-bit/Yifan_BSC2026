# 6. Per-segment metrics

**File**: `src/crackgraph/edge_metrics.py` (609 lines)

**What it does.** For **every segment** (`path_index`), it measures length, width and area. The
crack-stats export (page 5) gives one number per image; this file gives one per segment. It's
part of the per-image analysis (`analyze_image.py`), and its results go to a CSV file.

Crack width matters scientifically: earlier cracks tend to end up wider, because the film keeps
shrinking as it dries after they open. That makes width one of the three "clocks" in
`METHODOLOGY.md`. Don't confuse it with the *poset width w*, a different concept with the same
name (see `GLOSSARY.md`).

**Four area estimates, kept separate.** Pixels where several segments meet (the junction "blob")
don't clearly belong to any one segment, so no single area number is exact. Instead, the file
brackets the truth:

| Estimate | Where | Meaning | Guarantee |
|---|---|---|---|
| `area_core_px2` | per segment | Area outside every junction blob | **Proven** lower bound |
| `area_px2` | per segment | Each crack pixel assigned to its nearest segment (watershed) | The main estimate |
| `mask_clean_total_px2` | whole image | All crack pixels | **Proven** upper bound |
| `area_ribbon_px2` | per segment | Width × length, added up along the segment | Usually high, not guaranteed |

## Settings, lines 54–69

The comments sit *below* each setting here.

| Setting | Value | Meaning |
|---|---|---|
| `WIDTH_TRIM_INNER_PX_PLACEHOLDER` | 5 px | Skip this much at each end of a segment when measuring width, or the local half-width if that's bigger, so junction blobs and tapering tips don't skew it. 🔴 |
| `AREA_JUNCTION_BLOB_RADIUS_PLACEHOLDER` | 5 px | Radius of the "disputed zone" around each junction, widened the same way. 🔴 |

## Result containers, lines 72–149

- `EdgeWidthMeasurement`: width statistics for one segment (mean, median, min, max, spread),
  or a failure reason.
- `WatershedAreaResult`: which segment owns each crack pixel.
- `JunctionBlobAmbiguity`: for one junction, how many of its blob pixels each segment claimed.
- `EdgeMetrics`: all of the above for one segment.
- `EdgeMetricsResult`: every segment plus image-wide totals.

---

## `measure_edge_width(...)`, line 167

1. Get the segment's pixels and their distance along the segment (`s`, arc length).
2. Work out how much to trim at each end: 5 px, or the half-width at that end if bigger
   (`_effective_trim`, line 161).
3. Keep only the pixels between the two trims (line 212).
4. If nothing is left, report `"edge_too_short_for_trim"` instead of a contaminated number.
5. Otherwise, look up 2 × half-width at each kept pixel and summarize.

## `partition_area_by_edge(...)`, line 240: who owns which crack pixel

This uses a **watershed**. Picture each segment's centre line as a spring, and water flooding
outward from all springs at once across the crack. Each pixel belongs to the spring whose water
reaches it first.

| Line | What happens |
|---|---|
| 261–274 | Seed the flood from each segment's *interior* pixels, not its end pixels. Ends are shared between segments at a junction, and seeding them would give an arbitrary owner. Very short segments (2 pixels or fewer) have no interior, so they seed from their ends and are counted. |
| 276 | `watershed(-medial_radius, markers=..., mask=mask_clean)`: flood "downhill" from the centre line (largest half-width) outward, only through crack pixels. |
| 278–280 | Count each segment's pixels, all segments in one pass over the label image (`np.bincount`). |
| 283 | Pixels nobody reached: specks that were pruned away. |

## `estimate_edge_area_ribbon(...)`, line 292

It adds up width × step length along the segment's full path (trapezoid rule), giving the area
of a ribbon of the measured width. It runs high near junctions, because each segment credits
itself the whole wide blob.

## Junction disks, lines 310–425

- **`_iter_junction_disks`** (302): for each junction (degree ≥ 3), the crack pixels within its
  disk. It's shared by the next two functions so they can never disagree about which pixels are
  disputed.
- **`compute_junction_blob_ambiguity`** (340): for each junction disk, how many pixels the
  watershed gave to each segment. Labelled `[interpreted]`, because which segment "wins" a blob
  pixel depends on flood order, not physics.
- **`compute_ambiguous_pixel_mask`** (381): the same disks as one image, for drawing.
- **`compute_core_area`** (403): segment area minus its disputed pixels, never below 0. A short
  segment between two close junctions can come out at 0; that's reported as "no defensible core
  area".

## `compute_edge_metrics(...)`, line 428: the main function

It runs the watershed and the junction tallies once. Then it loops over segments (line 479) to
measure width, look up areas, and compute the ribbon estimate. It also keeps the image totals:
- total length
- length-weighted mean width
- how often the ribbon ran high or low
- crack length density (length ÷ image area, in px⁻¹)

## `write_edge_metrics_csv(...)`, line 577

One CSV row per segment.

## Worth knowing

- **Segments next to a flaking cut**: pass them as `exclude_from_stats`. They keep their row,
  marked `near_flaking_cut`, but stay out of total length, the width counts and the mean width,
  the same rule as the batch exporter. `analyze_image.py` does this.
- **Tests**: `tests/test_edge_metrics.py` (12 tests) checks widths on bands of known thickness
  and that the four area estimates bracket correctly. To see the four methods side by side, run
  `scripts/validation/render_area_method_viewer.py`.
