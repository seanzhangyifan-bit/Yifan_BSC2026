# Crack stats — column reference

## 1. Purpose & scope

The crack stats are the `crack_stats` measurement of the analysis tool (`src/crackgraph/measures/crack_stats.py`,
run from the GUI or `python3 -m src.analyze`). They use stages 1–3 of the pipeline (binarize →
skeletonize → graph extraction, plus flaking exclusion) and give one row of summary numbers per
image and region: identification/provenance, crack area, crack width, segment length, and
network-connectivity ("percolation") statistics, in pixels plus a calibrated µm/mm² twin where
applicable. Curvature/tortuosity and anisotropy are separate measurements of the same tool; they
add their own columns when chosen.

The columns land in the `regions` sheet of `results.xlsx`. With the default settings (whole
image, all column groups, 0.6098 µm/px) the numbers are exactly those of the earlier exporter,
`scripts/batch_stats/export_crack_stats.py`, archived 2026-11-13. `scripts/batch_stats/export_crack_stats_batch_bcd.py`
writes the same rows for three fixed thesis batches (B: T5 gap height on PTFE, C: T5 dew point on
membrane, D: T2/T3/T4 membrane), with an extra `batch` column.

§9 maps eight of the columns to the notation used in the thesis. §4d covers regions other than
the whole image.

## 2. Which images are analysed

The tool does **not** pick images by file name. It gives rows to every image file (`.jpg`,
`.jpeg`, `.png`, `.tif`, `.tiff`, `.bmp`) you name on the command line, in any subfolder of a
folder you name, or that you upload in the GUI. Choosing *which* images belong in a table is your
job.

## 4. Column reference

| # | Column | Definition | Unit | Tag |
|---|---|---|---|---|
| 1 | `image_filename` | Row identifier — see §3 | — | — |
| 2 | `source_folder` | Which `data/raw/` subfolder the image lives in — see §3 for the full list of 7 | — | — |
| 3 | `image_width_px` | Original raw image width | px | `measured` |
| 4 | `image_height_px` | Original raw image height | px | `measured` |
| 5 | `scale_bar_check` | `no blue bar (visually confirmed)` only when the run was started with `--scale-bars-checked`, i.e. someone did the direct per-image visual check described in §2 (not the naming-convention inference). Otherwise `not checked`, which is also what the GUI always writes. | text | — |
| 6 | `crack_area_pct` | `corrected_mask.sum() ÷ (image_width_px × image_height_px) × 100` — share of image pixels classified as crack by Otsu thresholding, after flaking exclusion (§4b) and mask cleaning: bright spots below `min_object_px` (light shining through the catalyst layer) filled, and dark specks inside cracks below `DARK_SPECK_AREA_PX` (pieces of catalyst layer or dust) removed. | % of image area | `measured` |
| 7 | `crack_area_mm2` | `crack_area_px² × (0.6098 µm/px)² ÷ 1e6` | mm² | `calibrated` |
| 8 | `avg_width_px` | `crack_area_px² ÷ total_skeleton_length_px` (length excluding omitted edges, §4b) — an area-based width estimate, **not** the distance-transform-sampled width used elsewhere in this pipeline. See §caveat below. | px | `interpreted` |
| 9 | `avg_width_um` | `avg_width_px × 0.6098` | µm | `calibrated` |
| 10 | `avg_edge_length_px` | `total_skeleton_length_px ÷ n_edges`, both excluding omitted edges (§4b) — mean distance between one graph node (junction or endpoint) and the next. **Not** "average crack length" — see §caveat below. | px | `measured` |
| 11 | `avg_edge_length_um` | `avg_edge_length_px × 0.6098` | µm | `calibrated` |
| 12 | `n_components` | Number of disconnected pieces in the crack network (graph connected-components count). The graph is built from the kept edges only: edges touching a flaked region are omitted (§4b), so nothing connects through a flaked patch. | count | `measured` |
| 13 | `giant_component_fraction` | (total crack length in the single largest connected piece) ÷ (total crack length, all pieces) — 1.0 means one fully connected web; well below 1 means fragmented into separate islands. Uses the same kept-edge graph as column 12. Every segment counts, including two segments that join the same pair of junctions; exports made before 2026-11-11 dropped one of each such pair and read slightly low (see `CHANGELOG.md`). | fraction, 0–1 | `measured` |
| 14 | `flaking_excluded_area_pct` | Share of image area excluded as flaking/delamination — see §4b | % of image area | `measured` |
| 15 | `flaking_n_candidates` | Number of flaking regions identified (width-flagged, grown to their true boundary) — see §4b | count | `interpreted` |
| 16 | `flaking_n_edges_omitted` | Number of skeleton edges with at least one pixel inside a flaked region, omitted from every statistic and from the connectivity graph — see §4b | count | `measured` |
| 17 | `n_host_stubs_pruned` | Number of dead-end skeleton branches removed during stage 2 pruning because less than 15 px (9.1 µm) of their length lies outside the crack they branch from, rather than because they were short overall — see §4c. Named `n_corner_artifacts_pruned` (a different, correlation-based rule) in exports made before 2026-11-11 | count | `interpreted` |
| 18 | `crack_area_pct_excl_flakes` | `crack_area_px² ÷ (image_width_px × image_height_px × (1 − flaking_excluded_area_pct ÷ 100)) × 100` — same numerator as column 6, but the denominator excludes the flaking-exclusion area (column 14, converted back to pixels) instead of counting the whole image, since that region is missing material, not confirmed non-crack, and there's zero evidence what (if anything) was under it before it flaked off. Equals column 6 exactly wherever `flaking_excluded_area_pct` is 0. | % of non-excluded image area | `measured` |
| 19 | `median_width_px` | Median of `2 × medial_radius` sampled at every pixel of every skeleton edge not omitted for touching a flaked region (same exclusion columns 8-11 use) — a genuine per-pixel distance-transform measurement, unlike column 8's area/length ratio. | px | `interpreted` |
| 20 | `median_width_um` | `median_width_px × 0.6098` | µm | `calibrated` |
| 21 | `median_edge_length_px` | Median `branch_distance` over edges not omitted for touching a flaked region — median rather than column 10's mean, same reasoning as column 19. | px | `interpreted` |
| 22 | `median_edge_length_um` | `median_edge_length_px × 0.6098` | µm | `calibrated` |
| 23 | `median_edge_length_gc_px` | Same as column 21, restricted to edges whose both endpoints lie in the giant component (column 13's component, chosen by summed edge length). | px | `interpreted` |
| 24 | `median_edge_length_gc_um` | `median_edge_length_gc_px × 0.6098` | µm | `calibrated` |
| 25 | `giant_component_span_px` | Straight-line distance between the two farthest-apart points on the giant component's own skeleton pixel path (every pixel of every edge inside it, not just its junction/endpoint nodes) — physical spatial reach, distinguishing a large multi-crack network from a single long crack. `NaN` only when the graph is entirely empty (no edges at all) — see the closed-loop caveat below for why sampling the full pixel path, not just node coordinates, matters. | px | `interpreted` |
| 26 | `giant_component_span_um` | `giant_component_span_px × 0.6098` | µm | `calibrated` |
| 27– | `runtime_binarize_s`, `runtime_skeletonize_s`, `runtime_flaking_s`, `runtime_graph_extract_s`, (`runtime_curvature_s`, `runtime_anisotropy_s` when those run), `runtime_measure_regions_s`, `runtime_total_s` | Only with the runtime option. Wall-clock time per stage, per image: every region row of one image repeats them. `runtime_total_s` is timed separately, so it can exceed the sum of the others. Before 2026-11-13, `runtime_measure_regions_s` was `runtime_stats_s`. | s | `measured` |

**Caveats that matter for correct use:**

- **`avg_width_px`** (column 8) is a crude cross-check estimate (total area ÷ total length), not
  a direct per-pixel measurement — **`median_width_px`** (column 19) is that direct measurement.
  On the 39-image set the two formulas cross-check to ~6.6% agreement in aggregate (crude version
  reading slightly lower) — treat that as a rough sanity check, not a guarantee for every image;
  report actual per-image agreement when both columns are present rather than assuming it holds.
- **`avg_edge_length_px`** answers "how far apart are two junctions/endpoints, on average" — it
  is the mean length of one atomic graph edge, not the mean length of a whole physical crack (a
  crack passing straight through several junctions without arresting there counts as several
  short edges, not one long one). It is also deflated by short junction-to-junction edges:
  0–55.2% of all edges per image are shorter than the image's own crack width
  (`scripts/validation/skeleton_loop_sweep.py`), weakly correlated with crack width, not
  substrate-dependent. This inflates `n_edges` (the denominator here) for affected images.
  Corrected 2026-11-11: these were attributed to thinning leaving spurious loops. A check on
  centre crops of all 41 images found only 8% of them next to a dark speck (a real loop); the
  rest are short segments between closely spaced junctions, some split crossings, some real
  geometry. See `docs/walkthrough/02_skeleton.md`.
- **`n_components` / `giant_component_fraction`** only see pieces that survived this pipeline's
  own mask cleaning and spur-pruning (isolated fragments and dead-end spurs shorter than a fixed
  pixel threshold are removed before this analysis ever runs) — "components at least
  roughly-a-crack-length long," not literally every disconnected mark in the raw image.
- **`giant_component_span_px`/`um`** (columns 25-26) samples every skeleton pixel on every edge
  inside the giant component, not just its junction/endpoint node coordinates. This matters for a
  giant component that's a single closed crack loop with no junctions at all — skan represents
  that as one node with a self-loop edge, so a node-coordinate-only span would be undefined (one
  point) even though the loop has real physical extent. Seen in practice on `T5-PTFE_H50_v2`
  (§9): giant component = 1 node, a 312-pixel closed-loop path spanning a ~107×108px bounding
  box — sampling the full path gives a real ~70µm span, where a node-only approach would have
  returned `NaN`.
- **`median_edge_length_gc_px`/`um`** and **`giant_component_span_px`/`um`** both use the giant
  component chosen by summed edge length (same definition as `giant_component_fraction`, column
  13) — a component can have fewer nodes than another and still be "the giant component" if its
  total length is greater.

### 4b. Flaking/delamination exclusion (columns 14-16)

Some samples (seen so far on membrane-substrate T2/T3/T4) have patches where the catalyst layer
has physically flaked off, exposing substrate underneath — bright under Otsu thresholding like a
real crack, but it's a 2D area of missing material, not a 1D fracture, and there's zero evidence
what crack pattern (if any) existed under the now-missing material. Left uncorrected, this
inflates `crack_area_pct` and corrupts `avg_width_px`/`avg_edge_length_px` (skeletonizing a
flaked blob's filled interior produces a genuinely multi-branched medial axis).

`src/crackgraph/flaking.py` identifies candidate regions by local width alone (far exceeding the
image's own typical crack width) — a solidity-based second criterion was tried and dropped after
it excluded a real elongated delamination case (solidity 0.674, confirmed genuine by inspection)
— and grows each candidate back out to its true boundary via mask-constrained dilation.

The mask is skeletonized **once**, flaked regions included. Any skeleton edge with at least one
pixel inside a flaked region is then **omitted** — from every statistic and from the connectivity
graph (`flaking_n_edges_omitted`). Omitting it from the graph matters: a flaked blob's own
skeleton is a multi-branched mesh that ordinary spur pruning can't remove, and left in, it would
falsely connect two real crack networks through a region with no evidence about what was there.
Crack area (`crack_area_pct`, columns 6–7 and 18) counts the cleaned mask minus the flaked
regions.

**Known gap, not yet fixed**: small, compact false positives from ordinary junction-blob
widening (not real flaking) can still pass the width+area test alone — see `flaking.py`'s module
docstring. `flaking_n_candidates` should be read as "candidates passing the current width test,"
not a confirmed count of real flaking regions.

**A consequence of skeletonizing once.** `n_host_stubs_pruned` counts pruning over the whole
mask, so it includes branches pruned inside flaked blobs.

### 4c. Host-stub pruning (column 17)

Thinning sends a branch from a crack's centre line into every bump, notch or corner on its wall,
whatever the branch's length, so fixed-length spur pruning misses the longer ones on wide cracks.
`src/crackgraph/skeleton.py` removes a dead end if less than `spur_px` (15 px = 9.1 µm) of its
length lies outside the crack it branches from: a stub runs from the centre line to the wall and
stops, a real side crack leaves the host. Removed branches are pruned from the skeleton entirely,
so they affect edge counts and the length statistics the same way spur pruning always has; there
is no "excluded but topology kept" treatment, because these are not real edges.

Before 2026-11-11 this column was `n_corner_artifacts_pruned` and counted branches removed by a
different rule (width rising steadily along the branch, correlation > 0.99). The two counts are
not comparable, and exports made before that date have lower `ledge` on dense wide-crack images
(see `CHANGELOG.md`). Full rationale: `docs/walkthrough/02_skeleton.md`.

### 4d. Regions other than the whole image

Every row starts with four region columns, placed after `source_folder`:

| Column | Definition |
|---|---|
| `region` | `whole`, `centre`, or `cell N (rRcC)`: grid cell N, numbered row by row from the top left. |
| `region_rows_px`, `region_cols_px` | The region's first and last pixel row and column (the stop value is exclusive). |
| `region_area_pct` | The region's share of the whole image's area. |

The image is analysed once; a region selects part of that one result (see
`docs/walkthrough/06_regions.md`). For a region that isn't the whole image:

- **Pixel quantities count the pixels inside the region**: `crack_area_pct`,
  `crack_area_pct_excl_flakes`, `crack_area_mm2`, `flaking_excluded_area_pct`, `avg_width_px`
  (its total length is the crack length inside the region), and `median_width_px`. "% of image
  area" in the table above then means % of the region's area. Grid cells add up to the whole image.
- **Segment quantities take each segment whole**, assigned to the region holding its middle
  pixel: `avg_edge_length_px`, `median_edge_length_px`, `flaking_n_edges_omitted`,
  `n_host_stubs_pruned`. A flaked patch counts in `flaking_n_candidates` where its bounding box's
  centre lies.
- **Connectivity is whole-image only** (`n_components`, `giant_component_fraction`,
  `median_edge_length_gc_px`, `giant_component_span_px` and their µm twins). Cutting the network
  at a region border splits it, so a region's connectivity would mostly reflect the region's
  size. When the regions don't include the whole image and connectivity is chosen, these columns
  go to a separate `image_connectivity` sheet, one row per image.

**Column groups.** The columns come in groups you can choose: `area` (6, 7, 18), `width` (8, 9,
19, 20), `segment_length` (10, 11, 21, 22), `connectivity` (12, 13, 23–26), `flaking` (14–16),
`pruning` (17). The identification columns (1–5 and the region columns) are always there.

**Calibration.** Every `_um`/`_mm2` column uses the µm per pixel set for the run, recorded in the
workbook's `settings` sheet. The "× 0.6098" in the table above is the default.

## 5. Evidence-level legend

Reused from this project's own convention:

- **`measured`** — read directly off the pixels/graph, no model or threshold beyond what earlier
  pipeline stages already assume.
- **`interpreted`** — a stated formula or approximation was applied on top of measured quantities.
- **`calibrated`** — depends on a physical px→µm conversion factor sourced from *outside* this
  repository (see §6). Held to a stricter standard of doubt than `measured`/`interpreted`, both
  of which are fully reproducible from this repo's own code.

## 6. Calibration disclosure

**Factor: `100 / 164 = 0.609756... µm/px`**, for the `mm` (full-resolution mosaic) tag only.
Derived by measuring the burned-in "100.00 µm" scale bar's pixel length across 56 mosaic frames
(median = 164px).

**Source**: an external calibration tool (`figlib/calibration.py`, `calibration.json`) that is
not part of this repository. This value is a hand-carried snapshot of that tool's output — not
derived by this codebase. If this repo ever imports that tool directly,
`figlib.calibration.um_per_px("mm")` should replace this hardcoded constant as the live source of
truth.

**Scope**: valid for the `mm` tag only. Single-tile magnifications (`100x`/`200x`/`300x`/`500x`/`800x`)
are different optical magnifications with their own factors entirely (e.g. 500x = 0.2882 µm/px,
800x = 0.1815 µm/px) — never apply 0.6098 to those.

**Cross-family assumption, not independently verified**: 27 of the 39 rows come from experiment
families (Aquivion T2, Characterization2) that this factor was not originally derived against —
the 56-frame median underlying it was measured only on frames from the families in `data/raw/`
before those rows existed. It is applied to those 27 rows on the assumption that `mm` = the same
stitching/capture setting across all experiment families (a microscope/software setting, not a
sample property) — not independently re-derived or re-verified. Those rows'
`image_width_px`/`image_height_px` do fall within the same range as the frames the factor was
measured on, which is consistent with (but doesn't prove) the assumption holding.

**Known-bad frames — one confirmed, one still open**: two frames are mistagged as `mm` but
aren't the standard mosaic capture, and would read roughly 2x too small if calibrated with
0.6098. One is fully identified (`.../Digital_v2/75RH_PTFE_v2_D_mm000000.jpg`, note the `D_`
prefix and `000000` index) — don't analyse it: the export doesn't detect it, and its calibrated
columns would be wrong. The second flagged file's exact path was never confirmed. If an image
looks like it could be that second bad frame, treat its `calibrated` columns as unreliable until
confirmed either way.

## 7. Data quality note: 23 of 39 rows fall outside the old 1–15% crack-fraction band

*The numbers in this section come from an export made before 2026-11-11, with the earlier flaking and pruning methods (see `CHANGELOG.md`). Re-export before quoting them.*

The Otsu-threshold step used to carry a built-in sanity check: `crack_area_pct` was expected to
fall roughly between 1% and 15% (a band read off a small non-PTFE sample set, never derived).
**23 of the 39 rows in this workbook fall outside that band** — a plain majority. The band did
not generalize past the original T5/humidity-loading sample set it was tuned on, so it was
removed from the code on 2026-11-11 (see `CHANGELOG.md`). The table below is kept because the
very low rows (near 0%) are still worth a look on their own; read the high rows as normal
variation, not as data-quality problems.

| `image_filename` | `source_folder` | `crack_area_pct` | `giant_component_fraction` | Read |
|---|---|---|---|---|
| `T5-PTFE_H50_v1_mm000001.jpg` | characterization2_ptfe | 0.04% | 0.437 | Near-zero area, and unlike the other near-zero row below, the crack network isn't even mostly-one-piece — weakest signal of the whole set. |
| `T5-PTFE_H50_v2_mm000001.jpg` | characterization2_ptfe | 0.13% | 0.031 | Near-zero area agrees with `v1` (0.04%), but connectivity reads very differently (`v1` gcf 0.44 vs `v2` gcf 0.03) — both replicates agree "very little crack," disagree on how fragmented it is. |
| `0RH_PTFE_v1_mm000001.jpg` | humidity_loading_ptfe | 0.12% | 0.031 | Area and connectivity agree — very little crack, mostly disconnected fragments. Plausibly real (0% RH = least drying stress), not obviously a segmentation failure. |
| `T1-N_PTFE_v2_IL70_mm000001.jpg` | aquivion_t2_ptfe | 0.65% | 0.011 | Same pattern: low area, almost no connectivity. |
| `T1-N_PTFE_v3_IL70_mm000001.jpg` | aquivion_t2_ptfe | 0.14% | 0.033 | Near-zero, poorly connected — consistent with this sample's other two replicates (`v1`: 1.06%, `v2`: 0.65%), all low-density and poorly connected. |
| `T2-A_PTFE_v2_IL70_mm000001.jpg` | aquivion_t2_ptfe | 0.55% | 0.005 | Near-zero, almost no connectivity — same "essentially unpercolated" pattern as its `v1` pair (3.39%, gcf 0.013). |
| `T4-M_v1_mm000001.jpg` | characterization2_membran | 22.78% | 0.975 | Well over the ceiling, but well-connected — consistent with every other Membran-substrate row below, not an isolated outlier. |
| `T4-M_v2_mm000001.jpg` | characterization2_membran | 23.47% | 0.977 | Same pattern as `v1` (22.78%). |
| `T4-M_H95_v1_mm000001.jpg` | characterization2_membran | 24.83% | 0.983 | Same pattern. |
| `T4-M_H95_v2_mm000001.jpg` | characterization2_membran | 22.44% | 0.990 | Same pattern as `v1` (24.83%). |
| `T3-M_v1_mm000001.jpg` | characterization2_membran | 25.15% | 0.989 | Same pattern. |
| `T3-M_v2_mm000001.jpg` | characterization2_membran | 25.02% | 0.987 | Same pattern as `v1` (25.15%). |
| `T3-M_H95_v1_mm000001.jpg` | characterization2_membran | 17.16% | 0.970 | Above ceiling, well-connected — same Membran-substrate pattern as every other row in this folder. |
| `T3-M_H95_v2_mm000001.jpg` | characterization2_membran | 15.68% | 0.936 | Just above ceiling, well-connected — consistent with its `v1` pair. |
| `T2-A_membran_v1_mm000001.jpg` | aquivion_t2_membran | 25.81% | 0.957 | Same pattern — every Membran-substrate row reads well above the ceiling. |
| `T2-A_membran_v2_mm000001.jpg` | aquivion_t2_membran | 27.97% | 0.980 | Same pattern as `v1` (25.81%). |
| `T4-PTFE_v1_mm000001.jpg` | characterization2_ptfe | 28.66% | 0.930 | Same high-area/well-connected pattern, PTFE substrate this time. |
| `T4-PTFE_v2_mm000001.jpg` | characterization2_ptfe | 28.08% | 0.934 | Same pattern as `v1` (28.66%). |
| `T3-PTFE_v1_mm000001.jpg` | characterization2_ptfe | 28.72% | 0.928 | Same pattern. |
| `T3-PTFE_v2_mm000001.jpg` | characterization2_ptfe | 26.89% | 0.926 | Same pattern as `v1` (28.72%). |
| `T5-PTFE_H190_v1_mm000001.jpg` | characterization2_ptfe | 29.40% | 0.978 | Same pattern. |
| `T5-PTFE_H190_v2_mm000001.jpg` | characterization2_ptfe | 28.58% | 0.972 | Same pattern as `v1` (29.40%). |
| `75RH_PTFE_v1_mm000001.jpg` | humidity_loading_ptfe | 33.43% | 0.963 | Same pattern. |

Every flagged row is either near-zero-and-poorly-connected (6 rows, low
`giant_component_fraction`) or well-above-the-ceiling-and-well-connected (17 rows, high
`giant_component_fraction`, entirely `characterization2_*`/`aquivion_t2_*` folders) — none are
outside the band *and* internally inconsistent (high area with low connectivity, or vice versa).
That internal consistency is a weak positive signal for these being real measurements of
genuinely more/less cracked samples rather than segmentation failures, but it is not a substitute
for someone with domain knowledge of these samples confirming that.

These are flagged here, not silently dropped or corrected. All 39 rows are included in the
workbook as computed regardless of band status.

## 7b. Data quality note: 23RH_PTFE_v1 uses mm000003, not the default mm000001

`23RH_PTFE_v1_mm000001.jpg` is an outlier: 4429×3322 px, visibly smaller than every other row's
~7300×7600 px. This sample has four `mm`-indexed captures, not the usual two — `mm000000` and
`mm000001` are *both* the undersized 4429×3322 capture, so the default "just use `000001`" rule
picks the wrong pair for this one sample. `mm000002` and `mm000003` are both the standard
~7300×7600 size; `mm000002` carries the blue scale bar, `mm000003` doesn't.

**The `23RH_PTFE_v1` row therefore used `mm000003`** instead of the default index. Its `image_width_px`/`image_height_px` (7263 / 7544) fall
within the same range as every other row, and the µm calibration factor applies normally — this
row uses a standard-sized mosaic capture like the rest.

## 8. Worked example — one full row, by hand

*The numbers in this section come from an export made before 2026-11-11, with the earlier flaking and pruning methods (see `CHANGELOG.md`). Re-export before quoting them.*

`T5-M_H190_v1_mm000001.jpg`, image size 7328 × 7612 px (full image = 55,777,536 px):

```
foreground_fraction        = 0.144631                       [measured]
crack_area_pct             = 0.144631 * 100 = 14.4631%
crack_area_px2             = 0.144631 * 7328 * 7612 = 8,067,604 px2
crack_area_mm2             = 8,067,604 * 0.609756^2 / 1e6 ≈ 2.9996 mm2      [calibrated]

total_skeleton_length_px   = 358,377.0 px  (sum of graph_result.summary['branch_distance'))
n_edges                    = 1,893
avg_edge_length_px         = 358,377.0 / 1,893 = 189.32 px                  [measured]
avg_edge_length_um         = 189.32 * 0.609756 ≈ 115.44 µm                  [calibrated]

avg_width_px               = 8,067,604 / 358,377.0 = 22.51 px               [interpreted]
avg_width_um               = 22.51 * 0.609756 ≈ 13.73 µm                    [calibrated]

n_components                = 27
giant_component_fraction    = 0.9967   -- 27 separate crack fragments exist, but 99.67% of all
                                          crack length belongs to one dominant connected network:
                                          this sample reads as essentially fully percolated.
```

All figures above matched the corresponding cells of that export to within rounding.

## 9. Thesis notation

The thesis tables use eight of the columns above under shorter names (`thesis_stats.xlsx`: these
eight plus `image_filename`/`source_folder`). The mapping:

| thesis name | source column | notes |
|---|---|---|
| `crack` (%) | `crack_area_pct_excl_flakes` | a real methodology correction over the legacy `crack_area_pct`, not a rename — the denominator excludes the flaking-excluded area |
| `flaking` (%) | `flaking_excluded_area_pct` | direct rename, no formula change |
| `wcrack` (µm) | `median_width_um` | a real methodology correction over the legacy `avg_width_px` — a true per-pixel median, not a global area/length ratio; excludes omitted edges, as the other width/length stats do |
| `N` (-) | `n_components` | direct rename |
| `fgc` (-) | `giant_component_fraction` | direct rename, formula unchanged |
| `ledge` (µm) | median (not mean) edge length, whole image | |
| `ledge,gc` (µm) | same median, restricted to giant-component edges | |
| `dgc` (µm) | giant component's own physical spatial reach — straight-line distance between its two farthest points, sampled from every skeleton pixel in the component | see the closed-loop caveat in §4's caveat list |

**Known caveat, not yet resolved**: `T5-PTFE_H50_v1`/`v2` have unusually low foreground fraction
(0.02%-0.13%, already flagged in §7) and the largest `median_width_px`/`avg_width_px` divergence
in the batch (-27%) — worth a direct visual check before trusting, since a network this sparse is
exactly where a global area/length ratio and a true per-pixel median are expected to diverge most.
