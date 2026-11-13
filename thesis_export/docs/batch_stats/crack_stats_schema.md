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
- §9 maps eight columns to the thesis notation.

## 2. Columns

`0.6098` below is the default µm per pixel; every run uses the value in its `settings` sheet.

| # | Column | Definition | Unit | Tag |
|---|---|---|---|---|
| 1 | `image_filename` | File name. | — | — |
| 2 | `source_folder` | Folder holding the image. | — | — |
| 3 | `image_width_px` | Raw image width. | px | `measured` |
| 4 | `image_height_px` | Raw image height. | px | `measured` |
| 5 | `scale_bar_check` | `no blue bar (visually confirmed)` only if the run used `--scale-bars-checked`; else `not checked` (always in the GUI). | text | — |
| 6 | `crack_area_pct` | Crack pixels ÷ image pixels × 100. Crack = Otsu foreground, bright spots filled, dark specks below `DARK_SPECK_AREA_PX` removed, flaked patches excluded (§3). | % | `measured` |
| 7 | `crack_area_mm2` | Crack pixels × 0.6098² ÷ 10⁶. | mm² | `calibrated` |
| 8 | `avg_width_px` | Crack area ÷ total skeleton length (kept segments). An area/length estimate. | px | `interpreted` |
| 9 | `avg_width_um` | `avg_width_px` × 0.6098. | µm | `calibrated` |
| 10 | `avg_edge_length_px` | Mean segment length (node to next node), kept segments. Not mean crack length. | px | `measured` |
| 11 | `avg_edge_length_um` | × 0.6098. | µm | `calibrated` |
| 12 | `n_components` | Number of separate pieces of the crack network, built from kept segments only. | count | `measured` |
| 13 | `giant_component_fraction` | Length of the largest piece ÷ total length. 1 = one connected web. Counts parallel segments between the same two junctions (exports before 2026-11-11 read slightly low). | 0–1 | `measured` |
| 14 | `flaking_excluded_area_pct` | Flaked area ÷ image area × 100 (§3). | % | `measured` |
| 15 | `flaking_n_candidates` | Flaked patches found (§3). | count | `interpreted` |
| 16 | `flaking_n_edges_omitted` | Segments with a pixel in a flaked patch, left out of everything (§3). | count | `measured` |
| 17 | `n_host_stubs_pruned` | Dead ends removed because less than 15 px (9.1 µm) lies outside their host crack (§3). Before 2026-11-11: `n_corner_artifacts_pruned`, a different rule. | count | `interpreted` |
| 18 | `crack_area_pct_excl_flakes` | Crack pixels ÷ (image pixels − flaked pixels) × 100. Equals column 6 without flaking. | % | `measured` |
| 19 | `median_width_px` | Median of 2 × half-width at every pixel of every kept segment. A direct per-pixel width. | px | `interpreted` |
| 20 | `median_width_um` | × 0.6098. | µm | `calibrated` |
| 21 | `median_edge_length_px` | Median segment length, kept segments. | px | `interpreted` |
| 22 | `median_edge_length_um` | × 0.6098. | µm | `calibrated` |
| 23 | `median_edge_length_gc_px` | As column 21, giant component only. | px | `interpreted` |
| 24 | `median_edge_length_gc_um` | × 0.6098. | µm | `calibrated` |
| 25 | `giant_component_span_px` | Distance between the giant component's two farthest pixels. `NaN` only for an empty graph. | px | `interpreted` |
| 26 | `giant_component_span_um` | × 0.6098. | µm | `calibrated` |
| 27– | `runtime_*_s` | Optional. Time per stage, per image (binarize, skeletonize, flaking, graph_extract, curvature, anisotropy, measure_regions, total). Before 2026-11-13, `measure_regions` was `stats`. | s | `measured` |

## 3. Notes on the columns

**Width (8, 19).**
- `avg_width_px` is a cross-check; `median_width_px` is the direct measurement.
- On the 39-image set they agree to about 6.6% in aggregate. Check per image; don't assume it.

**Segment length (10, 21).**
- A segment runs between two nodes. A crack crossing several junctions counts as several segments.
- 0–55% of segments per image are junction-to-junction segments shorter than the crack width
  (`scripts/validation/skeleton_loop_sweep.py`). They lower the mean. Only 8% are loops around
  dark specks; most are segments between close junctions (`docs/walkthrough/02_skeleton.md`).

**Connectivity (12, 13, 23–26).**
- Counts only pieces that survived cleaning and spur pruning: "pieces at least about a crack
  length long".
- Giant component = largest summed length, not most nodes.
- The span uses every pixel, not only nodes: a closed loop with no junctions has one node but a
  real size (seen on `T5-PTFE_H50_v2`: one node, a 312 px loop, about 70 µm span).

**Flaking (6, 14–16, 18).**
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

**Host stubs (17).**
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
| 6, 7, 8, 14, 18, 19 (and µm twins) | Pixels inside the region. "% of image area" becomes % of region area. Cells add up to the whole image. |
| 10, 16, 17, 21 (and µm twins) | Whole segments, placed by their middle pixel. |
| 15 | Patches, placed by their bounding-box centre. |
| 12, 13, 23–26 | Not per region. Whole image only, in the `image_connectivity` sheet: cutting at a border splits the network. |

**Column groups** you can choose: `area` (6, 7, 18), `width` (8, 9, 19, 20), `segment_length`
(10, 11, 21, 22), `connectivity` (12, 13, 23–26), `flaking` (14–16), `pruning` (17). Columns 1–5
and the region columns are always included.

## 5. Evidence tags

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
- **Assumption**: 27 of 39 thesis rows come from families (Aquivion T2, Characterization2) the
  factor wasn't measured on. Applied assuming `mm` is the same capture setting everywhere. Their
  image sizes match, which is consistent with, not proof of, this.
- **Bad frames**: `75RH_PTFE_v2_D_mm000000.jpg` is mistagged `mm` and would read about 2× too
  small; don't analyse it. A second suspected bad frame was never identified.

## 7. Data quality: rows outside the old 1–15% crack-area band

*From an export made before 2026-11-11 (earlier flaking and pruning). Re-export before quoting.*

The removed sanity band (1–15%) flagged 23 of 39 rows. The band was never derived. Low rows are
still worth a look; high rows are normal variation.

| Image | Folder | `crack_area_pct` | `giant_component_fraction` | Read |
|---|---|---|---|---|
| `T5-PTFE_H50_v1` | characterization2_ptfe | 0.04% | 0.437 | Near zero, fragmented. Weakest signal of the set. |
| `T5-PTFE_H50_v2` | characterization2_ptfe | 0.13% | 0.031 | Agrees with v1 on area, not on fragmentation. |
| `0RH_PTFE_v1` | humidity_loading_ptfe | 0.12% | 0.031 | Little crack, disconnected. Plausible at 0% RH. |
| `T1-N_PTFE_v2_IL70` | aquivion_t2_ptfe | 0.65% | 0.011 | Low area, almost no connectivity. |
| `T1-N_PTFE_v3_IL70` | aquivion_t2_ptfe | 0.14% | 0.033 | Consistent with v1 (1.06%) and v2. |
| `T2-A_PTFE_v2_IL70` | aquivion_t2_ptfe | 0.55% | 0.005 | Consistent with v1 (3.39%, 0.013). |
| `T4-M_v1` | characterization2_membran | 22.78% | 0.975 | High, well connected, like all membrane rows. |
| `T4-M_v2` | characterization2_membran | 23.47% | 0.977 | As v1. |
| `T4-M_H95_v1` | characterization2_membran | 24.83% | 0.983 | As above. |
| `T4-M_H95_v2` | characterization2_membran | 22.44% | 0.990 | As v1. |
| `T3-M_v1` | characterization2_membran | 25.15% | 0.989 | As above. |
| `T3-M_v2` | characterization2_membran | 25.02% | 0.987 | As v1. |
| `T3-M_H95_v1` | characterization2_membran | 17.16% | 0.970 | As above. |
| `T3-M_H95_v2` | characterization2_membran | 15.68% | 0.936 | As v1. |
| `T2-A_membran_v1` | aquivion_t2_membran | 25.81% | 0.957 | As above. |
| `T2-A_membran_v2` | aquivion_t2_membran | 27.97% | 0.980 | As v1. |
| `T4-PTFE_v1` | characterization2_ptfe | 28.66% | 0.930 | High, well connected, on PTFE. |
| `T4-PTFE_v2` | characterization2_ptfe | 28.08% | 0.934 | As v1. |
| `T3-PTFE_v1` | characterization2_ptfe | 28.72% | 0.928 | As above. |
| `T3-PTFE_v2` | characterization2_ptfe | 26.89% | 0.926 | As v1. |
| `T5-PTFE_H190_v1` | characterization2_ptfe | 29.40% | 0.978 | As above. |
| `T5-PTFE_H190_v2` | characterization2_ptfe | 28.58% | 0.972 | As v1. |
| `75RH_PTFE_v1` | humidity_loading_ptfe | 33.43% | 0.963 | As above. |

- Every flagged row is either low and fragmented (6) or high and well connected (17). None is
  internally inconsistent: a weak sign these are real, not segmentation failures. Needs a domain
  check.
- All 39 rows were kept as computed.

**23RH_PTFE_v1 uses `mm000003`.** Its `mm000000`/`mm000001` are an undersized 4429×3322 capture.
`mm000002`/`mm000003` are standard size (7263 × 7544); `mm000002` has the scale bar. The factor
applies normally.

## 8. Worked example

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

## 9. Thesis notation

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

**Open caveat**: `T5-PTFE_H50_v1`/`v2` are very sparse (§7) and have the largest
`median_width_px` vs `avg_width_px` gap (−27%). Check them by eye before trusting.
