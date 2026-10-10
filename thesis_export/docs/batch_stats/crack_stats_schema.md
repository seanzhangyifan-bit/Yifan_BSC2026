# `crack_stats.xlsx` — column reference

## 1. Purpose & scope

`compute_row()` (`scripts/batch_stats/export_crack_stats.py`) runs stage 1-3 of the pipeline
(binarize → skeletonize → graph extraction, plus flaking exclusion) on one image and returns a
row of summary numbers: image identification/provenance, crack area, crack width, edge length,
and network-connectivity ("percolation") statistics — pixel units plus a physically-calibrated
secondary where applicable. It is deliberately **not** the full crack-graph pipeline output — no
junction classification (T/Y census), no anisotropy, no curvature, no crack-ordering/precedence
data. Those exist for a different purpose (reconstructing a partial order of crack growth from
junction geometry) and are out of scope here on purpose.

`compute_row()` backs three outputs today, all sharing the same column definitions (§4) unless a
section below says otherwise:

- **`crack_stats.xlsx`** — a 39-row snapshot, one row per raw micrograph in `data/raw/`. §2-§8
  describe this file specifically. Not a live feed; regenerate via
  `python3 -m scripts.batch_stats.export_crack_stats` to pick up any code changes.
- **`outputs/crack_stats_v2/`** — a 19-image re-run adding flaking-aware per-image caching and a
  thesis-notation column mapping. §9 describes it.
- **`outputs/crack_stats_v3_batch_bcd.xlsx`** — an independent, single-pass methodology
  (`scripts/batch_stats/export_crack_stats_v3.py`), cross-validated against v1/v2 rather than
  replacing them. §10 describes the methodology difference and validation result.

## 2. How images are selected

Raw filenames follow the pattern:

```
{sample}_{variant}_{lu|mm|ro}{000000|000001}.jpg
```

Every image was captured up to three times per sample/variant (`lu`, `mm`, `ro` — different
capture passes) at two indices. For the `mm` (full-resolution stitched mosaic) tag, the two
indices usually differ in content, not just in name: `mm000000` usually carries a burned-in blue
"100.00 µm" scale-bar annotation over a sparser field of view; `mm000001` is usually the clean
full-frame capture.

**This naming convention is necessary but not sufficient — it is a strong pattern, not a
guarantee.** Every `*_mm000001.jpg` file under `data/raw/` was directly viewed (bottom-right
corner crop) rather than trusted on the naming pattern alone. Two confirmed exceptions:

- **`T5-M_H190_v2_mm000001.jpg`** has a burned-in blue scale bar despite the `000001` index —
  excluded from the workbook entirely (`CONFIRMED_SCALE_BAR_IMAGES`).
- **`23RH_PTFE_v1`**'s `000000`/`000001` pair is itself an undersized, non-standard capture
  (4429×3322 px vs. the ~7300×7600 px every other row has). This sample has four `mm`-indexed
  captures on the source; `000002`/`000003` are the standard-sized pair, and `000002` carries the
  scale bar while `000003` doesn't — so this workbook uses **`23RH_PTFE_v1_mm000003.jpg`**
  instead of the default index (`ADDITIONAL_IMAGES`; see §7b for the width/height detail).

If this export is ever regenerated against a larger image set, re-verify every file by eye —
this pattern is confirmed capable of failing in more than one way, not a single guaranteed rule.

**Current scope**: 39 images across 7 `data/raw/` subfolders (§3), spanning the T5
Rakelspalt-gap series, the humidity-loading (NR212) series on both substrates, and the Aquivion
T2 / Characterization2 T3/T4 sample families. One filename detail worth flagging rather than
silently normalizing: some files carry an `_IL70_` infix (e.g.
`T1-N_PTFE_v2_IL70_mm000001.jpg`) — reads as a formulation/sample label (e.g. ionomer content),
not a capture-mode suffix; doesn't change which calibration factor applies (§6), passed through
in `image_filename` as-is for the reader to interpret.

**Why some samples have 2-3 rows and most have 1**: `v1`/`v2`/`v3` are separate physical
replicate captures of the same experimental condition — not a document-revision number and not
near-duplicate frames. This workbook includes every replicate that was captured and passed the
naming/visual checks above — it does not pick one "canonical" replicate per condition and
discard the rest. If you want per-condition statistics (mean ± SD), group rows by
`image_filename` with its trailing `_mm######.jpg` index stripped (e.g. `T5-M_H95_v1_mm000001.jpg`
and `T5-M_H95_v2_mm000001.jpg` both belong to group `T5-M_H95`), average only where ≥2 rows exist,
and report single-replicate groups as-is with no fabricated uncertainty. This is the same
grouping key (`_sample_id()`) the sibling `image_visualization` project's own `crack_levels_table`
figures already use — this workbook is built for that project to consume via its own
`figlib/crack_data.py`, and never hand-edited there; corrections happen in this repo and get
re-copied over.

One verification method worth flagging as rejected: an automated pixel-color-sampling check
(testing for blue-channel excess, to auto-detect the scale-bar overlay) reported *zero* scale
bars across an entire file class, including a file already confirmed by eye to have one — the
heuristic was simply wrong. Every file in this workbook was instead confirmed by directly viewing
the rendered image; don't trust a pixel-statistic scale-bar check without spot-checking it
against a known positive first.

## 3. Directory layout

`image_filename` is the file's basename only (e.g. `T5-M_H190_v1_mm000001.jpg`). In this repo,
and in any copy of `data/raw/` with the same structure, each file lives one level down under a
condition/experiment subfolder:

```
data/raw/
  T5/                          (Rakelspalt-gap condition series, Membran substrate: H190, H95)
  humidity_loading/            (NR212 reference membrane, filenames encode RH: 0RH/23RH/75RH)
  humidity_loading_ptfe/       (PTFE substrate, same RH encoding)
  aquivion_t2_membran/         (T1-N/T2-A samples, Membran substrate)
  aquivion_t2_ptfe/            (T1-N/T2-A samples, PTFE substrate)
  characterization2_membran/   (T3/T4 samples, Membran substrate)
  characterization2_ptfe/      (T3/T4/T5 samples, PTFE substrate)
```

The last four folders follow the same substrate-split convention already used for
`humidity_loading` vs. `humidity_loading_ptfe` — same experiment family, different substrate
goes in a different folder, rather than merging substrates into one folder and relying on the
filename alone to distinguish them.

`image_filename` alone is unique across this 39-row set; if merging against a larger set where
that stops being true, join on `(source_folder, image_filename)` instead — both are columns,
see §4.

## 4. Column reference

| # | Column | Definition | Unit | Tag |
|---|---|---|---|---|
| 1 | `image_filename` | Row identifier — see §3 | — | — |
| 2 | `source_folder` | Which `data/raw/` subfolder the image lives in — see §3 for the full list of 7 | — | — |
| 3 | `image_width_px` | Original raw image width | px | `measured` |
| 4 | `image_height_px` | Original raw image height | px | `measured` |
| 5 | `scale_bar_check` | Result of the direct per-image visual check described in §2 (not the naming-convention inference) | text | — |
| 6 | `crack_area_pct` | `corrected_mask.sum() ÷ (image_width_px × image_height_px) × 100` — share of image pixels classified as crack by Otsu thresholding, after flaking exclusion (§4b) and despeckling (tiny objects below `min_object_px` removed). | % of image area | `measured` |
| 7 | `crack_area_mm2` | `crack_area_px² × (0.6098 µm/px)² ÷ 1e6` | mm² | `calibrated` |
| 8 | `avg_width_px` | `crack_area_px² ÷ total_skeleton_length_px` (length excluding cut-adjacent edges, §4b) — an area-based width estimate, **not** the distance-transform-sampled width used elsewhere in this pipeline. See §caveat below. | px | `interpreted` |
| 9 | `avg_width_um` | `avg_width_px × 0.6098` | µm | `calibrated` |
| 10 | `avg_edge_length_px` | `total_skeleton_length_px ÷ n_edges`, both excluding cut-adjacent edges (§4b) — mean distance between one graph node (junction or endpoint) and the next. **Not** "average crack length" — see §caveat below. | px | `measured` |
| 11 | `avg_edge_length_um` | `avg_edge_length_px × 0.6098` | µm | `calibrated` |
| 12 | `n_components` | Number of disconnected pieces in the crack network (graph connected-components count). Uses the full graph including cut-adjacent edges — they're real topology, only their reported length is untrustworthy. | count | `measured` |
| 13 | `giant_component_fraction` | (total crack length in the single largest connected piece) ÷ (total crack length, all pieces) — 1.0 means one fully connected web; well below 1 means fragmented into separate islands. Also uses the full graph. | fraction, 0–1 | `measured` |
| 14 | `flaking_excluded_area_pct` | Share of image area excluded as flaking/delamination — see §4b | % of image area | `measured` |
| 15 | `flaking_n_candidates` | Number of flaking regions identified (width-flagged, grown to their true boundary) — see §4b | count | `interpreted` |
| 16 | `flaking_n_edges_excluded_near_cut` | Number of graph edges touching the flaking-exclusion boundary, dropped from the length/width stats above (columns 8-11) — see §4b | count | `measured` |
| 17 | `n_corner_artifacts_pruned` | Number of skeleton branches removed during stage 2 pruning because their width trends monotonically with position (a medial-axis branch tracing into a concave mask-boundary corner) rather than because they were short — see §4c | count | `interpreted` |
| 18 | `crack_area_pct_excl_flakes` | `crack_area_px² ÷ (image_width_px × image_height_px × (1 − flaking_excluded_area_pct ÷ 100)) × 100` — same numerator as column 6, but the denominator excludes the flaking-exclusion area (column 14, converted back to pixels) instead of counting the whole image, since that region is missing material, not confirmed non-crack, and there's zero evidence what (if anything) was under it before it flaked off. Equals column 6 exactly wherever `flaking_excluded_area_pct` is 0. | % of non-excluded image area | `measured` |
| 19 | `median_width_px` | Median of `2 × medial_radius` sampled at every pixel of every skeleton edge NOT touching the flaking-exclusion cut (same exclusion columns 8-11 use) — a genuine per-pixel distance-transform measurement, unlike column 8's area/length ratio. | px | `interpreted` |
| 20 | `median_width_um` | `median_width_px × 0.6098` | µm | `calibrated` |
| 21 | `median_edge_length_px` | Median `branch_distance` over edges NOT touching the flaking-exclusion cut — median rather than column 10's mean, same reasoning as column 19. | px | `interpreted` |
| 22 | `median_edge_length_um` | `median_edge_length_px × 0.6098` | µm | `calibrated` |
| 23 | `median_edge_length_gc_px` | Same as column 21, restricted to edges whose both endpoints lie in the giant component (column 13's component, chosen by summed edge length). | px | `interpreted` |
| 24 | `median_edge_length_gc_um` | `median_edge_length_gc_px × 0.6098` | µm | `calibrated` |
| 25 | `giant_component_span_px` | Straight-line distance between the two farthest-apart points on the giant component's own skeleton pixel path (every pixel of every edge inside it, not just its junction/endpoint nodes) — physical spatial reach, distinguishing a large multi-crack network from a single long crack. `NaN` only when the graph is entirely empty (no edges at all) — see the closed-loop caveat below for why sampling the full pixel path, not just node coordinates, matters. | px | `interpreted` |
| 26 | `giant_component_span_um` | `giant_component_span_px × 0.6098` | µm | `calibrated` |

**Caveats that matter for correct use:**

- **`avg_width_px`** (column 8) is a crude cross-check estimate (total area ÷ total length), not
  a direct per-pixel measurement — **`median_width_px`** (column 19) is that direct measurement.
  On the 39-image set the two formulas cross-check to ~6.6% agreement in aggregate (crude version
  reading slightly lower) — treat that as a rough sanity check, not a guarantee for every image;
  report actual per-image agreement when both columns are present rather than assuming it holds.
- **`avg_edge_length_px`** answers "how far apart are two junctions/endpoints, on average" — it
  is the mean length of one atomic graph edge, not the mean length of a whole physical crack (a
  crack passing straight through several junctions without arresting there counts as several
  short edges, not one long one). It is also deflated by a known skeletonization artifact:
  `skeleton.py`'s thinning step can trace both edges of a locally wide/irregular crack band
  before merging, leaving a small spurious loop instead of one clean line — measured across the
  full 39-image dataset at 0–55.2% of all edges per image (`scripts/validation/skeleton_loop_sweep.py`),
  weakly correlated with crack width, not substrate-dependent. This inflates `n_edges` (the
  denominator here) for affected images.
- **`n_components` / `giant_component_fraction`** only see pieces that survived this pipeline's
  own despeckling and spur-pruning (isolated fragments and dead-end spurs shorter than a fixed
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
— grows each candidate back out to its true boundary via mask-constrained dilation, and excludes
the result from the mask before skeletonization runs, so flaked pixels never contribute a
spurious skeleton at all.

**Known gap, not yet fixed**: small, compact false positives from ordinary junction-blob
widening (not real flaking) can still pass the width+area test alone — see `flaking.py`'s module
docstring. `flaking_n_candidates` should be read as "candidates passing the current width test,"
not a confirmed count of real flaking regions.

**Two ways an edge near a flaked region gets handled — v1 vs. v3, see §10**: `scripts/batch_stats/export_crack_stats.py`
(v1, the version §2-§9 describe) re-skeletonizes the corrected mask a second time, then drops any
edge whose path comes within one reference-crack-width of the exclusion boundary
(`flaking_n_edges_excluded_near_cut`) from the length/width stats only — it stays in the
connectivity graph, since it's a real truncated stub at an actual mask boundary. `scripts/batch_stats/export_crack_stats_v3.py`
(v3) instead skeletonizes once on the uncorrected mask and drops any edge with even one pixel
inside the excluded region from the connectivity graph itself, not just the stat columns — see
§10 for why (a single-pass graph would otherwise let a flaked blob's own interior mesh falsely
bridge two real crack networks).

### 4c. Corner-tracing artifact pruning (column 17)

The medial axis transform underlying skeletonization mathematically must trace a branch into
every concave corner of the mask boundary, regardless of length — this is a correct property of
the medial axis, not thinning noise, and it is blind to length, so fixed-length spur pruning does
not catch it. `src/crackgraph/skeleton.py` additionally flags a branch as this kind of artifact
if its local width (from the same distance transform used elsewhere in this pipeline) trends
monotonically with position along the branch (Pearson correlation vs. `CORR_THRESHOLD`, currently
0.99) rather than staying flat the way a genuine, noisy-but-stable-width crack does — see the
module docstring and `docs/calibration_notes.md` for the full derivation and rejected alternative
criteria. Flagged branches are pruned from the skeleton entirely, so they affect `crack_area_pct`,
`avg_width_px`, and `avg_edge_length_px` the same way real pruning always has — there is no
separate "excluded but topology kept" treatment here, unlike the flaking cut-adjacent case in
§4b, because these branches are not truncated real edges, they are not real edges at all.

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
prefix and `000000` index) — it can't appear in this workbook regardless, since row selection
(§2) only includes `000001`-indexed files. The second flagged file's exact path was never
confirmed. None of this workbook's filenames match the one confirmed bad-frame pattern, but none
can be positively cleared against the second, unconfirmed one either. If a future regeneration of
this file turns up a filename that looks like it could be that second bad frame, its three
`calibrated` columns should be treated as unreliable until confirmed either way.

## 7. Data quality note: 23 of 39 rows fall outside the expected crack-fraction band

This pipeline's Otsu-threshold step has its own built-in sanity check: `crack_area_pct` is
expected to fall roughly between 1% and 15% (a band read off a small non-PTFE sample set, not
re-derived here). **23 of the 39 rows in this workbook fall outside that band** — a plain
majority. That is the headline finding of this section: **the band, as currently set, does not
generalize past the original T5/humidity-loading sample set it was tuned on** — not that 23
images are individually suspect. Read the table below as "this sanity check needs re-tuning
against a wider sample," not as 23 separate data-quality problems.

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

**This workbook's `23RH_PTFE_v1` row therefore uses `mm000003`**, substituted in place of the
default index (`ADDITIONAL_IMAGES`). Its `image_width_px`/`image_height_px` (7263 / 7544) fall
within the same range as every other row, and the µm calibration factor applies normally — this
row uses a standard-sized mosaic capture like the rest.

## 8. Worked example — one full row, by hand

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

All figures above match the corresponding cells in `crack_stats.xlsx` to within rounding.

## 9. v2: 19-image re-run with flaking-aware caching and thesis notation

A separate 19-image batch (not the 39-row set above), re-run with a per-image analysis cache
(`outputs/crack_stats_v2/<image_stem>/`: `stats.json`, `mask_corrected.npz`,
`skeleton_final.npz`, `excluded_mask.npz`, `flaking_candidates.json`, `pruned_branches.npz`,
`overlay.png`) and a thesis-notation column mapping. `outputs/crack_stats_v2/crack_stats.xlsx`
keeps every internal column (same as §4); `outputs/crack_stats_v2/thesis_stats.xlsx` has just the
8 renamed/reworked columns below plus `image_filename`/`source_folder`.

| thesis name | source column | notes |
|---|---|---|
| `crack` (%) | `crack_area_pct_excl_flakes` | a real methodology correction over the legacy `crack_area_pct`, not a rename — the denominator excludes the flaking-excluded area |
| `flaking` (%) | `flaking_excluded_area_pct` | direct rename, no formula change |
| `wcrack` (µm) | `median_width_um` | a real methodology correction over the legacy `avg_width_px` — a true per-pixel median, not a global area/length ratio; excludes cut-adjacent edges same as the legacy width/length stats |
| `N` (-) | `n_components` | direct rename |
| `fgc` (-) | `giant_component_fraction` | direct rename, formula unchanged |
| `ledge` (µm) | median (not mean) edge length, whole image | |
| `ledge,gc` (µm) | same median, restricted to giant-component edges | |
| `dgc` (µm) | giant component's own physical spatial reach — straight-line distance between its two farthest points, sampled from every skeleton pixel in the component | see the closed-loop caveat in §4's caveat list |

**Known caveat, not yet resolved**: `T5-PTFE_H50_v1`/`v2` have unusually low foreground fraction
(0.02%-0.13%, already flagged in §7) and the largest `median_width_px`/`avg_width_px` divergence
in the batch (-27%) — worth a direct visual check before trusting, since a network this sparse is
exactly where a global area/length ratio and a true per-pixel median are expected to diverge most.

## 10. v3: independent single-pass methodology

`scripts/export_crack_stats_v3.py` is a second, independent implementation of the crack-stats
export, alongside `scripts/batch_stats/export_crack_stats.py` ("v1" by contrast) — both remain
runnable, neither replaces the other. The methodology difference is in how a flaked/delaminated
region gets excluded (see §4b):

- **v1** scout-skeletonizes once to get a reference crack width, grows a detected flake back to
  its true boundary, subtracts it from the mask, and skeletonizes a **second time** on the
  corrected mask. Edges within one reference-width of the flake boundary are dropped from
  length/width stats but kept in the connectivity graph, since in this two-pass design they're
  real truncated stubs at an actual mask boundary.
- **v3** skeletonizes **once**, on the uncorrected mask, then omits any edge with even one pixel
  inside the excluded region from the graph itself — not just the stat columns. This matters
  because a single-pass graph's flaked-blob interior is inherently multi-branched and
  structurally un-prunable by ordinary spur/fragment pruning; left in the connectivity graph, it
  would falsely bridge two real crack networks that only "connect" through a region with zero
  evidence about what was actually there.

**Disclosed semantic gaps versus v1 (not bugs, not being fixed)**: `crack_area_px2` isn't
re-cleaned after subtraction (v1's second skeletonize pass re-despeckles; v3 reuses the mask
directly), so v1/v3 area numbers on flaked images differ in the 5th significant figure, not
bit-identical. A v3 `--cache-dir`'s `mask_corrected.npz` does not correspond to what was actually
skeletonized (v3's skeleton comes from the uncorrected mask) — don't point a v3 cache directory
at a v1/v2 one. `n_corner_artifacts_pruned` reflects pruning on the flake-inclusive mask, so it
mixes real-crack pruning with however much of the blob's interior noise got pruned along the way.
v3 adds six per-stage timing columns (`runtime_binarize_s`, `runtime_skeletonize_s`,
`runtime_flaking_s`, `runtime_graph_extract_s`, `runtime_stats_s`, `runtime_total_s`).

**Validation**: on the 13 images the v2 and v3 batches happen to share, area/width/length columns
agree closely (`crack_area_pct_excl_flakes`/`flaking_excluded_area_pct` match to within 0.01%
everywhere — same flaking-detection call in both). Connectivity columns
(`n_components`/`giant_component_span_um`/width) show mean absolute differences of 2-4.5% (max
30-37%, concentrated on the images with the most flaking) — tracking the disclosed methodology
difference above exactly, and nowhere else. Full numeric comparison and per-column charts:
https://claude.ai/code/artifact/94529aca-a2a9-4d6f-b24d-459f58a7e690
