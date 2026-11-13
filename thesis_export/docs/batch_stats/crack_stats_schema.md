# Crack stats: column reference

## 1. Scope

- The `crack_stats` measurement (`src/crackgraph/measures/crack_stats.py`), run from the GUI or
  `python3 -m src.analyze`.
- Uses binarize → skeletonize → flaking exclusion → graph. One row per image and region, in the
  `regions` sheet of `results.xlsx`.
- Default settings (whole image, all groups, 0.6098 µm/px) give exactly the numbers of the earlier
  exporter (`export_crack_stats.py`, archived 2026-11-13).
- `scripts/batch_stats/export_crack_stats_batch_bcd.py`: the same rows for thesis batches B, C, D,
  plus a `batch` column.
- Images: every file you name, upload or put in a named folder. Nothing is selected by file name.
- Images must not carry a burned-in scale bar (some thesis `mm000000` files have a blue
  "100.00 µm" bar). The tool doesn't detect one: a bar would be counted as crack. Check by eye.
- §8 maps eight columns to the thesis notation.

## 2. Columns

`0.6098` below is the default µm per pixel; every run uses the value in its `settings` sheet.

| # | Column | Definition | Unit | Tag |
|---|---|---|---|---|
| 1 | `image_filename` | File name. | — | — |
| 2 | `source_folder` | Folder holding the image. | — | — |
| 3 | `image_width_px` | Raw image width. | px | `measured` |
| 4 | `image_height_px` | Raw image height. | px | `measured` |
| 5 | `crack_area_pct` | Crack pixels ÷ image pixels × 100. Crack = Otsu foreground, bright spots filled, dark specks below `DARK_SPECK_AREA_PX` removed, flaked patches excluded (§3). | % | `measured` |
| 6 | `crack_area_mm2` | Crack pixels × 0.6098² ÷ 10⁶. | mm² | `calibrated` |
| 7 | `avg_width_px` | Crack area ÷ total skeleton length (kept segments). An area/length estimate. | px | `interpreted` |
| 8 | `avg_width_um` | `avg_width_px` × 0.6098. | µm | `calibrated` |
| 9 | `avg_edge_length_px` | Mean segment length (node to next node), kept segments. Not mean crack length. | px | `measured` |
| 10 | `avg_edge_length_um` | × 0.6098. | µm | `calibrated` |
| 11 | `n_components` | Number of separate pieces of the crack network, built from kept segments only. | count | `measured` |
| 12 | `giant_component_fraction` | Length of the largest piece ÷ total length. 1 = one connected web. Counts parallel segments between the same two junctions (exports before 2026-11-11 read slightly low). | 0–1 | `measured` |
| 13 | `flaking_excluded_area_pct` | Flaked area ÷ image area × 100 (§3). | % | `measured` |
| 14 | `flaking_n_candidates` | Flaked patches found (§3). | count | `interpreted` |
| 15 | `flaking_n_edges_omitted` | Segments with a pixel in a flaked patch, left out of everything (§3). | count | `measured` |
| 16 | `n_host_stubs_pruned` | Dead ends removed because less than 15 px (9.1 µm) lies outside their host crack (§3). Before 2026-11-11: `n_corner_artifacts_pruned`, a different rule. | count | `interpreted` |
| 17 | `crack_area_pct_excl_flakes` | Crack pixels ÷ (image pixels − flaked pixels) × 100. Equals column 5 without flaking. | % | `measured` |
| 18 | `median_width_px` | Median of 2 × half-width at every pixel of every kept segment. A direct per-pixel width. | px | `interpreted` |
| 19 | `median_width_um` | × 0.6098. | µm | `calibrated` |
| 20 | `median_edge_length_px` | Median segment length, kept segments. | px | `interpreted` |
| 21 | `median_edge_length_um` | × 0.6098. | µm | `calibrated` |
| 22 | `median_edge_length_gc_px` | As column 20, giant component only. | px | `interpreted` |
| 23 | `median_edge_length_gc_um` | × 0.6098. | µm | `calibrated` |
| 24 | `giant_component_span_px` | Distance between the giant component's two farthest pixels. `NaN` only for an empty graph. | px | `interpreted` |
| 25 | `giant_component_span_um` | × 0.6098. | µm | `calibrated` |
| 26– | `runtime_*_s` | Optional. Time per stage, per image (binarize, skeletonize, flaking, graph_extract, curvature, anisotropy, measure_regions, total). Before 2026-11-13, `measure_regions` was `stats`. | s | `measured` |

## 3. Notes on the columns

**Width (7, 18).**
- `avg_width_px` is a cross-check; `median_width_px` is the direct measurement.
- On the 39-image set they agree to about 6.6% in aggregate.

**Segment length (9, 20).**
- A segment runs between two nodes. A crack crossing several junctions counts as several segments.
- 0–55% of segments per image are junction-to-junction segments shorter than the crack width
  (`scripts/validation/skeleton_loop_sweep.py`). They lower the mean. Only 8% are loops around
  dark specks; most are segments between close junctions (`docs/walkthrough/02_skeleton.md`).

**Connectivity (11, 12, 22–25).**
- Counts only pieces that survived cleaning and spur pruning: "pieces at least about a crack
  length long".
- Giant component = largest summed length, not most nodes.
- The span uses every pixel, not only nodes: a closed loop with no junctions has one node but a
  real size (seen on `T5-PTFE_H50_v2`: one node, a 312 px loop, about 70 µm span).

**Flaking (5, 13–15, 17).**
- Some samples (seen on membrane T2/T3/T4) have patches where the catalyst layer flaked off. They
  are bright like cracks but are missing material, with no evidence of what was underneath.
- `flaking.py` flags pixels far wider than the image's typical crack width and grows them out to
  the patch boundary. Width is the only criterion (a solidity test wrongly excluded a real
  elongated case).
- Skeletonized once. Every segment with a pixel in a patch is left out of every column and of the
  connectivity graph, so nothing connects through a patch.
- Known gap: small compact junction blobs can pass the width test. Read `flaking_n_candidates` as
  "candidates", not confirmed patches.
- `n_host_stubs_pruned` includes stubs pruned inside flaked patches.

**Host stubs (16).**
- Thinning draws a branch from a crack's centre line into each bump on its wall. A dead end with
  less than `spur_px` outside its host is such a stub and is removed; a real side crack leaves the
  host.
- Removed stubs are gone from the skeleton, like spurs.
- Not comparable with `n_corner_artifacts_pruned` (before 2026-11-11), which also had lower `ledge`
  on dense wide-crack images.

## 4. Regions other than the whole image

Region columns, after `source_folder`:

| Column | Definition |
|---|---|
| `region` | `whole`, `centre` or `cell N (rRcC)`, cells numbered row by row from the top left. |
| `region_rows_px`, `region_cols_px` | First and last pixel row and column (stop exclusive). |
| `region_area_pct` | The region's share of the image area. |

The image is analysed once; a region selects part of that result (`docs/walkthrough/06_regions.md`).

| Columns | Counted in a region by |
|---|---|
| 5, 6, 7, 13, 17, 18 (and µm twins) | Pixels inside the region. "% of image area" becomes % of region area. Cells add up to the whole image. |
| 9, 15, 16, 20 (and µm twins) | Whole segments, placed by their middle pixel. |
| 14 | Patches, placed by their bounding-box centre. |
| 11, 12, 22–25 | Not per region. Whole image only, in the `image_connectivity` sheet: cutting at a border splits the network. |

**Column groups** you can choose: `area` (5, 6, 17), `width` (7, 8, 18, 19), `segment_length`
(9, 10, 20, 21), `connectivity` (11, 12, 22–25), `flaking` (13–15), `pruning` (16). Columns 1–4
and the region columns are always included.

## 5. Evidence tags

A rough heuristic for how much interpretation sits between the pixels and a number, assigned by
judgement. Not a quantified uncertainty.

- **`measured`**: read off the pixels or graph.
- **`interpreted`**: a stated formula or approximation on top of measured values.
- **`calibrated`**: depends on the µm-per-pixel factor, which comes from outside this repository
  (§6).

## 6. Calibration

- **Default factor**: 100 / 164 = 0.6098 µm/px, `mm` (stitched mosaic) images only. From the
  burned-in 100 µm scale bar, median 164 px over 56 frames.
- **Source**: an external tool (`figlib/calibration.py`), not this repository. A hand-copied
  value.
- **Not for** single-tile magnifications (e.g. 500x = 0.2882, 800x = 0.1815 µm/px). Set your own
  µm per pixel for those.

## 7. Worked example

*From an export made before 2026-11-11. Re-export before quoting.*

`T5-M_H190_v1_mm000001.jpg`, 7328 × 7612 px:

```
crack_area_pct           = 0.144631 × 100 = 14.4631 %
crack_area_px2           = 0.144631 × 7328 × 7612 = 8,067,604 px²
crack_area_mm2           = 8,067,604 × 0.609756² / 1e6 ≈ 2.9996 mm²

total length             = 358,377.0 px,  n_edges = 1,893
avg_edge_length_px       = 358,377.0 / 1,893 = 189.32 px  (≈ 115.44 µm)
avg_width_px             = 8,067,604 / 358,377.0 = 22.51 px (≈ 13.73 µm)

n_components             = 27
giant_component_fraction = 0.9967  (99.67% of the length in one network)
```

All values matched that export to rounding.

## 8. Thesis notation

| Thesis | Column | Note |
|---|---|---|
| `crack` (%) | `crack_area_pct_excl_flakes` | Denominator excludes flaked area. |
| `flaking` (%) | `flaking_excluded_area_pct` | |
| `wcrack` (µm) | `median_width_um` | Per-pixel median, not area/length. |
| `N` (-) | `n_components` | |
| `fgc` (-) | `giant_component_fraction` | |
| `ledge` (µm) | `median_edge_length_um` | Median, not mean. |
| `ledge,gc` (µm) | `median_edge_length_gc_um` | Giant component only. |
| `dgc` (µm) | `giant_component_span_um` | Every pixel, see §3. |
