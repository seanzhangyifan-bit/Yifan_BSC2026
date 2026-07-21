# `crack_stats.xlsx` — column reference

## 1. Purpose & scope

This workbook is a one-time snapshot — 39 rows, one per raw micrograph, produced by running
`python3 -m scripts.export_crack_stats` against this repo's `data/raw/` on the date in the file's
own timestamp. It is **not** a live feed and does not update itself.

It covers 13 columns: image identification/provenance, crack area, crack width, average edge
length, and two network-connectivity ("percolation") numbers — the latter three each in raw pixel
units plus a physically-calibrated secondary where applicable. It is deliberately **not** the full
output of this repo's
crack-graph pipeline — no junction classification (T/Y census), no anisotropy, no curvature, no
crack-ordering/precedence data. Those exist for a different purpose (reconstructing a partial
order of crack growth from junction geometry) and are out of scope here on purpose, not by
oversight.

## 2. How the 24 rows were selected

Raw filenames in this project follow the pattern:

```
{sample}_{variant}_{lu|mm|ro}{000000|000001}.jpg
```

Every image was captured up to three times per sample/variant (`lu`, `mm`, `ro` — different
capture passes) at two indices. For the `mm` (full-resolution stitched mosaic) tag specifically,
the two indices are **usually not** the same shot twice — they usually differ in content:

- `mm000000` usually carries a burned-in blue "100.00 µm" scale-bar annotation in the bottom-right
  corner, over what is visibly a different, sparser field of view than its `000001` sibling.
- `mm000001` is usually the clean full-frame capture, no overlay.

**This naming convention is necessary but not sufficient — it is a strong pattern, not a
guarantee.** Every `*_mm000001.jpg` file under `data/raw/` was directly viewed (bottom-right corner
crop) rather than trusted on the naming pattern alone, and it broke in two different ways:

- **`T5-M_H190_v2_mm000001.jpg`** has a burned-in blue scale bar despite the `000001` index. It is
  excluded from this workbook entirely (`scripts/export_crack_stats.py`'s
  `CONFIRMED_SCALE_BAR_IMAGES`).
- **`23RH_PTFE_v1`**'s `000000`/`000001` pair is *itself* an undersized, non-standard capture
  (4429&times;3322 px, vs. the ~7300&times;7600 px every other row has) — not a scale-bar problem,
  a wrong-pair problem. This sample actually has four `mm`-indexed captures on the source; `000002`
  and `000003` are the standard-sized pair, and `000002` carries the scale bar while `000003`
  doesn't. This workbook uses **`23RH_PTFE_v1_mm000003.jpg`** for that row instead of the default
  index (`scripts/export_crack_stats.py`'s `ADDITIONAL_IMAGES`) — see §7b.

If this export is ever regenerated against a larger image set, re-verify every file by eye — do not
extend the `000001`-only rule without checking. It is now confirmed capable of failing in more than
one way, not a single guaranteed pattern.

### 2b. Second batch: 12 new samples added (12 rows → 24)

A second round of candidate source paths was supplied covering two experiment families not
previously in this repo's `data/raw/`: `Pt Kat Aquivion T2` (samples `T1-N`, `T2-A`) and
`Pt Kat Characterization 2` (samples `T3`, `T4`, plus additional `T5` rows on the PTFE substrate —
the existing `T5/` folder only had the Membran substrate before this batch). Of 17 candidate paths:

- **5 were byte-identical duplicates** of files already in this workbook (confirmed by `md5sum`,
  not just filename match) — `T5-M_H190_v1`, `T5-M_H95_v1`, `0RH_NR212_v1`, `23RH_NR212_v1`,
  `75RH_NR212_v1`. Skipped, not re-copied or re-counted.
- **12 were genuinely new.** Each was directly viewed (same bottom-right-corner check as §2) —
  none carry a scale-bar overlay — and each is standard mosaic size (7244–7338 × 7532–7619 px,
  matching every other row's range; none of the `23RH_PTFE_v1`-style undersized-frame problem
  recurred here).

These 12 use the same `_mm000001.jpg` suffix as the existing rows, so no code change was needed —
`scripts/export_crack_stats.py`'s existing glob picked them up once copied into `data/raw/`.

One filename detail worth flagging rather than silently normalizing: two of the twelve carry an
`_IL70_` infix (`T1-N_PTFE_v2_IL70_mm000001.jpg`, `T2-A_PTFE_v1_IL70_mm000001.jpg`) not seen in any
prior filename in this repo. This reads as a formulation/sample label (e.g. ionomer content), not a
capture-mode or magnification suffix — it doesn't change which calibration factor applies (see §6),
but its exact meaning was not confirmed against thesis documentation and is passed through in
`image_filename` as-is for the reader to interpret.

### 2c. Why some samples have 2 rows (`v1` **and** `v2`) and most have 1

This workbook is built for a specific downstream consumer — a sibling project,
`image_visualization` (internally called `figlib`), a figure-making toolkit over the same
`all_pics/` source catalogue this repo's `data/raw/` is drawn from. It reads this file through its
own `figlib/crack_data.py` and never hand-edits it; if that repo's copy of this file or the schema
doc looks stale, the fix happens here and gets re-copied over, not the reverse.

**`v1`/`v2` (and any `v3`+ elsewhere in the source catalogue) are separate physical replicate
captures of the same experimental condition — not a document-revision number and not
near-duplicate frames of each other.** This matches the definition already established in that
sibling repo's own catalogue guide: "Replicate/version number of that same sample... each `v#` is
a physically distinct imaged region or repeat sample." Some conditions were imaged twice; most were
imaged once. Both are real facts about the underlying data collection, not an inconsistency in this
export.

**This workbook includes every replicate that was captured and passed the §2/§2b checks — it does
not pick one "canonical" replicate per condition and discard the rest.** As of the 24-row set, 4
conditions have 2 rows each — `T5-M_H95`, `0RH_NR212`, `23RH_NR212`, `75RH_NR212` (all `v1`+`v2`
pairs) — and every other condition has exactly 1 row.

**If you want per-condition statistics (e.g. mean ± SD), group rows by `image_filename` with its
trailing `_mm######.jpg` index stripped** — e.g. `T5-M_H95_v1_mm000001.jpg` and
`T5-M_H95_v2_mm000001.jpg` both belong to the group `T5-M_H95`. This is exactly the grouping key
(`_sample_id()`) `figlib/crack_data.py` already uses. Average within a group only where ≥2 rows
exist; report single-replicate groups as-is with no fabricated uncertainty. This is precisely what
`figlib`'s own `crack_levels_table` figures do (e.g. `configs/t5_humidity/t5_humidity_crack_stats.yaml`,
`configs/t5_gap_series/t5_gap_crack_stats.yaml`): real replicate pairs get a visible ± SD,
single-replicate rows get none — "an honest reflection of what's actually there, not a fabricated
uncertainty," in that config's own words.

**Gap closed in §2d below**: the batch above left 3 of its 12 samples with un-copied replicate
siblings sitting in the source catalogue — `T1-N_PTFE` (`v1`/`v2`/`v3` on the source, only `v2` was
in this workbook), `T2-A_Membran` (`v1`/`v2`, only `v1` included), `T2-A_PTFE` (`v1`/`v2`, only `v1`
included). This was a scope decision at the time, not an oversight. §2d closes this gap, and also
folds in one further gap that surfaced while closing it (`T3-M_H95`, never onboarded at all).

### 2d. Third batch: 15 more rows added (24 rows → 39), humidity families explicitly excluded

Closed the gap flagged in §2c: `v2`/`v3` replicates for the Aquivion T2 and Characterization 2
families that existed in the source catalogue but had never been copied into `data/raw/`. Per the
requester's explicit direction, the humidity-loading families (`humidity_loading/`,
`humidity_loading_ptfe/`) were left untouched in this batch — no `v2` replicates were sought or
added there, regardless of what exists on the source for them.

15 new files, all `_mm000001.jpg`, each directly viewed (same bottom-right-corner check as §2) —
**none carry a blue scale-bar overlay**, and all fall within the standard ~7245–7350 × 7523–7629 px
range (no `23RH_PTFE_v1`-style undersized-frame problem recurred). One verification wrinkle worth
recording: an automated pixel-color-sampling check (testing for blue-channel excess) was tried
first and reported *zero* scale bars across this entire file class, including on a file
(`T5-M_H190_v2_mm000001.jpg`) already known and documented (§2) to have one — the heuristic was
simply wrong. Every file in this batch was instead confirmed by directly viewing the rendered image,
the same standard this doc has used throughout — don't trust a pixel-statistic scale-bar check
without spot-checking it against a known positive first.

What this batch closed:

- **`T1-N_PTFE`**: added `v1` and `v3` (previously only `v2` was in the workbook) — now has all
  three source replicates.
- **`T2-A_Membran`**, **`T2-A_PTFE`**: added `v2` (previously only `v1`) — now `v1`+`v2` each.
- **`T3-M_H95`**: a fully new sample, not merely a `v2` gap — this sample had **zero** rows in
  `data/raw/` before this batch; source has `v1`+`v2`, no `v3`. Added both. The source folder is
  named `T3_M_H95` (underscore) while its files are named `T3-M_H95_*` (hyphen) — a plausible reason
  this sample was missed when the §2b batch was assembled by scanning folder names. The `v1` file
  itself was visually checked and looks like every other clean sample (no scale bar, ordinary crack
  pattern) — no sign it was skipped for a quality reason, just skipped.
- **`T3-M`, `T4-M`, `T4-M_H95`, `T3-PTFE`, `T4-PTFE`, `T5-PTFE_H50`, `T5-PTFE_H95`,
  `T5-PTFE_H145`, `T5-PTFE_H190`**: added `v2` (previously only `v1`) — now `v1`+`v2` each.

**Checked, confirmed no gap, left alone**: the `T5/` Rakelspalt family (`T5-M_H190`, `T5-M_H95`)
already had both `v1` and `v2` `mm000001` files copied in before this batch — nothing to add.

**Checked, found, deliberately not added** (out of stated scope, flagged so it isn't rediscovered
by a future session): `T2-M_H90`, a Characterization2 sample with `v1`+`v2` on the source, was never
onboarded at all — not even `v1`. This is a new-sample gap, not a replicate gap, and this batch's
scope was Characterization2's `T3`/`T4`/`T5` samples only. Also worth flagging if this sample is
ever added: its two source files disagree on their own naming — the `v1` file is
`T2-A_M_H90_v1_mm000001.jpg` (with a stray `-A`) while `v2` is `T2-M_H90_v2_mm000001.jpg` (without
it).

**Replicate-consistency bonus**: this batch is the first time most of these Characterization2/
Aquivion-T2 samples have both `v1` and `v2` `crack_area_pct` values to compare. Most pairs agree
well (e.g. `T3-M`: 25.15% vs 25.02%; `T4-PTFE`: 28.66% vs 28.08%; `T5-PTFE_H50`: both near-zero at
0.04% and 0.13% area — reinforcing that this condition's low crack density is plausibly real, not a
one-off segmentation miss, though see below). `T5-PTFE_H145` disagrees more than most (11.01% vs
14.11% area, `giant_component_fraction` 0.75 vs 0.91) — still the same qualitative regime, but
flagged as the largest same-condition spread seen among replicate pairs so far. `T5-PTFE_H50`'s two
replicates also disagree on connectivity despite agreeing on area: `giant_component_fraction` 0.44
(`v1`) vs 0.03 (`v2`) — both readings agree "very little crack," but disagree sharply on how
fragmented that little crack is. This is an observation, not a re-derivation of §7's band discussion
below.

## 3. Directory layout

`image_filename` is the file's basename only (e.g. `T5-M_H190_v1_mm000001.jpg`). In this repo, and
in any copy of `data/raw/` with the same structure, each file lives one level down under a
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
`humidity_loading` vs. `humidity_loading_ptfe` — same experiment family, different substrate goes
in a different folder, rather than merging substrates into one folder and relying on the filename
alone to distinguish them.

`image_filename` alone is unique across this 39-row set; if merging against a larger set where
that stops being true, join on `(source_folder, image_filename)` instead — both are now columns,
see §4.

## 4. Column reference

| # | Column | Definition | Unit | Tag |
|---|---|---|---|---|
| 1 | `image_filename` | Row identifier — see §3 | — | — |
| 2 | `source_folder` | Which `data/raw/` subfolder the image lives in — see §3 for the full list of 7 | — | — |
| 3 | `image_width_px` | Original raw image width | px | `measured` |
| 4 | `image_height_px` | Original raw image height | px | `measured` |
| 5 | `scale_bar_check` | Result of the direct per-image visual check described in §2 (not the naming-convention inference) | text | — |
| 6 | `crack_area_pct` | `corrected_mask.sum() ÷ (image_width_px × image_height_px) × 100` — share of image pixels classified as crack by Otsu thresholding, **after** flaking exclusion (see §4b) and despeckling (tiny objects below `min_object_px` removed). Was `binarize_result.foreground_fraction` (the raw, uncorrected mask) before flaking exclusion existed — see §4b for the size of that correction. | % of image area | `measured` |
| 7 | `crack_area_mm2` | `crack_area_px² × (0.6098 µm/px)² ÷ 1e6` | mm² | `calibrated` |
| 8 | `avg_width_px` | `crack_area_px² ÷ total_skeleton_length_px` (length excluding cut-adjacent edges, §4b) — an area-based width estimate, **not** the distance-transform-sampled width used elsewhere in this pipeline. See §caveat below. | px | `interpreted` |
| 9 | `avg_width_um` | `avg_width_px × 0.6098` | µm | `calibrated` |
| 10 | `avg_edge_length_px` | `total_skeleton_length_px ÷ n_edges`, both **excluding cut-adjacent edges** (§4b) — mean distance between one graph node (junction or endpoint) and the next. **Not** "average crack length" — see §caveat below. | px | `measured` |
| 11 | `avg_edge_length_um` | `avg_edge_length_px × 0.6098` | µm | `calibrated` |
| 12 | `n_components` | Number of disconnected pieces in the crack network (graph connected-components count). Uses the **full** graph including cut-adjacent edges — they're real topology, only their reported length is untrustworthy, not their existence. | count | `measured` |
| 13 | `giant_component_fraction` | (total crack length in the single largest connected piece) ÷ (total crack length, all pieces) — 1.0 means the network is one fully connected web; well below 1 means it's still fragmented into separate islands. Also uses the full graph, same reasoning as `n_components`. | fraction, 0–1 | `measured` |
| 14 | `flaking_excluded_area_pct` | Share of image area excluded as flaking/delamination — see §4b | % of image area | `measured` |
| 15 | `flaking_n_candidates` | Number of flaking regions identified (width-flagged, grown to their true boundary) — see §4b | count | `interpreted` |
| 16 | `flaking_n_edges_excluded_near_cut` | Number of graph edges touching the flaking-exclusion boundary, dropped from the length/width stats above (columns 8-11) — see §4b | count | `measured` |

**Caveats that matter for correct use:**

- **`avg_width_px`** is a crude cross-check estimate (total area ÷ total length), not the more
  detailed distance-transform width used elsewhere in this pipeline. On real images the two methods
  agreed to within ~6.6%, in a consistent direction (this crude version reads slightly lower) — close
  enough to trust as a width estimate, but treat the two as *different formulas that happen to agree
  closely*, not identical numbers.
- **`avg_edge_length_px`** answers "how far apart are two junctions/endpoints, on average" — it is
  the mean length of one atomic graph edge, not the mean length of a whole physical crack (a crack
  that passes straight through several junctions without arresting there would count as several
  short edges, not one long one). It is also **deflated by a known skeletonization artifact**:
  `skeleton.py`'s thinning step can trace both edges of a locally wide/irregular crack band before
  merging, leaving a small spurious loop (two short extra edges) instead of one clean line — measured
  across the full 39-image dataset at 0–55.2% of all edges per image (`scripts/skeleton_loop_sweep.py`),
  weakly correlated with crack width, not substrate-dependent. This directly inflates `n_edges` (the
  denominator here) for affected images. See `README.md`'s "Pipeline status" section for the full
  mechanism and numbers — not re-derived here, this is a pointer, not a duplicate.
- **`n_components` / `giant_component_fraction`** only see pieces that survived this pipeline's own
  despeckling and spur-pruning (isolated fragments and dead-end spurs shorter than a fixed pixel
  threshold are removed before this analysis ever runs). These are "components at least
  roughly-a-crack-length long," not literally every disconnected mark in the raw image.

### 4b. Flaking/delamination exclusion (columns 14-16)

Some samples (seen so far on membrane-substrate T2/T3/T4) have patches where the catalyst layer has
physically flaked off, exposing substrate underneath — bright under Otsu thresholding like a real
crack, but it's a 2D area of missing material, not a 1D fracture, and we have zero evidence what
crack pattern (if any) existed under the now-missing material. Left uncorrected, this inflated
`crack_area_pct` and corrupted `avg_width_px`/`avg_edge_length_px` (skeletonizing a flaked blob's
filled interior produces a genuinely multi-branched medial axis — a different mechanism from the
double-line loop artifact above, since a blob-shaped region's skeleton is inherently branchy, not a
thinning artifact).

`src/crackgraph/flaking.py` identifies candidate regions (local width far exceeding the image's own
typical crack width — width is the single identification criterion, deliberately; an earlier version
also required high solidity to separate compact blobs from elongated crack bands, but that was
dropped after a real elongated candidate, solidity 0.674, was confirmed by inspection to be genuine
delamination — solidity was excluding real cases), grows each one back out to its true boundary via
mask-constrained dilation, and excludes the result from the mask *before* the real skeletonization
runs — so flaked pixels never contribute a spurious skeleton at all. Graph edges whose path comes
within one reference-crack-width of the exclusion boundary at any point (`flaking_n_edges_excluded_near_cut`,
not just an edge's two endpoint nodes — an endpoint-only check measurably misses edges that graze the
exclusion mid-path without terminating there) are truncation artifacts of the cut, not real crack
arrests, so they're dropped from the length/width statistics (columns 8-11) but kept in the
connectivity graph for columns 12-13, since their topology is real even though their reported length
isn't.

**Known gap, not yet fixed**: small, compact false positives from ordinary junction-blob widening
(not real flaking) can still pass the width+area test alone — see `flaking.py`'s module docstring.
`flaking_n_candidates` should therefore be read as "candidates passing the current width test," not
as a confirmed count of real flaking regions — spot-check by eye before trusting it on a new image
the way every other selection criterion in this doc has been.

## 5. Evidence-level legend

Reused from this project's own convention:

- **`measured`** — read directly off the pixels/graph, no model or threshold beyond what earlier
  pipeline stages already assume.
- **`interpreted`** — a stated formula or approximation was applied on top of measured quantities.
- **`calibrated`** — depends on a physical px→µm conversion factor sourced from *outside* this
  repository (see §6). Held to a stricter standard of doubt than `measured`/`interpreted`, both of
  which are fully reproducible from this repo's own code.

## 6. Calibration disclosure

**Factor: `100 / 164 = 0.609756... µm/px`**, for the `mm` (full-resolution mosaic) tag only.
Derived by measuring the burned-in "100.00 µm" scale bar's pixel length across 56 mosaic frames
(median = 164px).

**Source**: an external calibration tool (`figlib/calibration.py`, `calibration.json`) that is not
part of this repository. This value is a hand-carried snapshot of that tool's output — not derived
by this codebase, and not re-derived by eye here. If this repo ever imports that tool directly,
`figlib.calibration.um_per_px("mm")` should replace this hardcoded constant as the live source of
truth.

**Scope**: valid for the `mm` tag only. Single-tile magnifications (`100x`/`200x`/`300x`/`500x`/`800x`)
are different optical magnifications with their own factors entirely (e.g. 500x = 0.2882 µm/px,
800x = 0.1815 µm/px) — never apply 0.6098 to those.

**Extension to the second batch (12 rows added, §2b)**: the 12 newly-added rows come from two
experiment families (`Pt Kat Aquivion T2`, `Pt Kat Characterization 2`) that this factor was not
originally derived against — the 56-frame median underlying it (below) was measured only on frames
from the families already in `data/raw/` before this batch. It is applied to these 12 rows on the
stated assumption that `mm` = the same stitching/capture setting across all experiment families
(a microscope/software setting, not a sample property) — **not independently re-derived or
re-verified for this batch.** All 12 new rows' `image_width_px`/`image_height_px` do fall within the
same range as the frames the factor was measured on, which is consistent with (but does not prove)
the assumption holding. **The third batch (§2d) adds 15 more rows from these same two already-
covered experiment families** — the same assumption and the same lack of independent
re-verification apply to them; no new calibration caveat is introduced.

**Known-bad frames — one confirmed, one still open**: two frames are mistagged as `mm` but aren't
the standard mosaic capture, and would read roughly 2x too small if calibrated with 0.6098. One is
fully identified (`.../Digital_v2/75RH_PTFE_v2_D_mm000000.jpg`, note the `D_` prefix and `000000`
index) — it can't appear in this workbook regardless, since row selection (§2) only includes
`000001`-indexed files. **The second flagged file's exact path arrived garbled in the message that
supplied this calibration factor and was never resent or confirmed.** None of this workbook's
filenames match the one confirmed bad-frame pattern, but none can be positively cleared against the
second, unconfirmed one either. If a future regeneration of this file turns up a filename that
looks like it could be that second bad frame, its three `calibrated` columns should be treated as
unreliable until confirmed either way.

## 7. Data quality note: 23 of 39 rows now outside the expected crack-fraction range

This pipeline's Otsu-threshold step has its own built-in sanity check: `crack_area_pct` is expected
to fall roughly between 1% and 15% (a band read off a small non-PTFE sample set, not re-derived
here). At 12 rows, 2 fell outside it (both `humidity_loading_ptfe`). After the second batch (§2b)
added 12 more rows across two new experiment families, **11 of the 24 rows fell outside the
band** — the flagged share jumped from 1-in-6 to nearly half. After the third batch (§2d) added 15
more rows to the same two experiment families, **23 of the 39 rows now fall outside the band** — a
plain majority. That continued drift is itself the headline finding of this section, now stronger
than before: **the band, as currently set, does not generalize past the original T5/humidity-loading
sample set it was tuned on** — not that 23 images are individually suspect. Read the numbers below
as "this sanity check needs re-tuning against a wider sample," not as 23 separate data-quality
problems.

| `image_filename` | `source_folder` | `crack_area_pct` | `giant_component_fraction` | Read |
|---|---|---|---|---|
| `T5-PTFE_H50_v1_mm000001.jpg` | characterization2_ptfe | 0.04% | 0.437 | Near-zero area, and unlike the other near-zero row below, the crack network isn't even mostly-one-piece — weakest signal of the whole set. |
| `0RH_PTFE_v1_mm000001.jpg` | humidity_loading_ptfe | 0.12% | 0.031 | Area and connectivity agree — very little crack, mostly disconnected fragments. Plausibly real (0% RH = least drying stress), not obviously a segmentation failure. |
| `T1-N_PTFE_v2_IL70_mm000001.jpg` | aquivion_t2_ptfe | 0.65% | 0.011 | Same pattern: low area, almost no connectivity. |
| `T4-M_v1_mm000001.jpg` | characterization2_membran | 22.78% | 0.975 | Well over the ceiling, but well-connected — consistent with the other Membran-substrate rows below, not an isolated outlier. |
| `T4-M_H95_v1_mm000001.jpg` | characterization2_membran | 24.83% | 0.983 | Same pattern. |
| `T3-M_v1_mm000001.jpg` | characterization2_membran | 25.15% | 0.989 | Same pattern. |
| `T2-A_membran_v1_mm000001.jpg` | aquivion_t2_membran | 25.81% | 0.957 | Same pattern — every Membran-substrate row added in the second batch reads well above the ceiling. |
| `T4-PTFE_v1_mm000001.jpg` | characterization2_ptfe | 28.66% | 0.930 | Same high-area/well-connected pattern, PTFE substrate this time. |
| `T3-PTFE_v1_mm000001.jpg` | characterization2_ptfe | 28.72% | 0.928 | Same pattern. |
| `T5-PTFE_H190_v1_mm000001.jpg` | characterization2_ptfe | 29.40% | 0.978 | Same pattern. |
| `75RH_PTFE_v1_mm000001.jpg` | humidity_loading_ptfe | 33.43% | 0.963 | Same pattern (already flagged at 12 rows). |

**Rows added in the third batch (§2d) that also fall outside the band:**

| `image_filename` | `source_folder` | `crack_area_pct` | `giant_component_fraction` | Read |
|---|---|---|---|---|
| `T1-N_PTFE_v3_IL70_mm000001.jpg` | aquivion_t2_ptfe | 0.14% | 0.033 | Near-zero, poorly connected — consistent with this sample's other two replicates (`v1`: 1.06%, `v2`: 0.65%), all low-density and poorly connected. |
| `T2-A_PTFE_v2_IL70_mm000001.jpg` | aquivion_t2_ptfe | 0.55% | 0.005 | Near-zero, almost no connectivity — same "essentially unpercolated" pattern as its `v1` pair (3.39%, gcf 0.013). |
| `T5-PTFE_H50_v2_mm000001.jpg` | characterization2_ptfe | 0.13% | 0.031 | Near-zero area agrees with `v1` (0.04%), but connectivity reads very differently (`v1` gcf 0.44 vs `v2` gcf 0.03) — both replicates agree "very little crack," disagree on how fragmented it is. |
| `T3-M_H95_v1_mm000001.jpg` | characterization2_membran | 17.16% | 0.970 | Above ceiling, well-connected — new sample (§2d), same Membran-substrate pattern as every other row in this folder. |
| `T3-M_H95_v2_mm000001.jpg` | characterization2_membran | 15.68% | 0.936 | Just above ceiling, well-connected — consistent with its `v1` pair. |
| `T3-M_v2_mm000001.jpg` | characterization2_membran | 25.02% | 0.987 | Same pattern as `v1` (25.15%). |
| `T4-M_H95_v2_mm000001.jpg` | characterization2_membran | 22.44% | 0.990 | Same pattern as `v1` (24.83%). |
| `T4-M_v2_mm000001.jpg` | characterization2_membran | 23.47% | 0.977 | Same pattern as `v1` (22.78%). |
| `T2-A_membran_v2_mm000001.jpg` | aquivion_t2_membran | 27.97% | 0.980 | Same pattern as `v1` (25.81%) — every Membran-substrate row, both replicates, reads well above the ceiling. |
| `T3-PTFE_v2_mm000001.jpg` | characterization2_ptfe | 26.89% | 0.926 | Same pattern as `v1` (28.72%). |
| `T4-PTFE_v2_mm000001.jpg` | characterization2_ptfe | 28.08% | 0.934 | Same pattern as `v1` (28.66%). |
| `T5-PTFE_H190_v2_mm000001.jpg` | characterization2_ptfe | 28.58% | 0.972 | Same pattern as `v1` (29.40%). |

Notice the split still holds at 23 rows: every flagged row is either near-zero-and-poorly-connected
(6 rows total now, low `giant_component_fraction`) or well-above-the-ceiling-and-well-connected (17
rows total now, high `giant_component_fraction`, entirely `characterization2_*`/`aquivion_t2_*`
folders) — none of the 23 are outside the band *and* internally inconsistent (high area with low
connectivity, or vice versa). That internal consistency is a weak positive signal for these being
real measurements of genuinely more/less cracked samples rather than segmentation failures, but it
is not a substitute for someone with domain knowledge of these samples confirming that.

These are flagged here, not silently dropped or corrected. All 39 rows are included in the workbook
as computed regardless of band status.

## 7b. Data quality note: 23RH_PTFE_v1 uses mm000003, not the default mm000001

This repo's own pipeline code (`src/analyze_image.py`) already flags `23RH_PTFE_v1_mm000001.jpg`
as an outlier: 4429 × 3322 px, visibly smaller than every other row's ~7300 × 7600 px. Checking the
source folder directly resolved why: this sample has **four** `mm`-indexed captures, not the usual
two. `mm000000` and `mm000001` are *both* the undersized 4429×3322 capture (so the default
"just use `000001`" rule silently picked the wrong pair for this one sample — not a scale-bar
problem, a wrong-pair problem). `mm000002` and `mm000003` are both the standard ~7300×7600 size;
directly viewed both — `mm000002` carries the blue scale bar, `mm000003` doesn't.

**This workbook's `23RH_PTFE_v1` row therefore uses `mm000003`**, substituted in place of the
default index (`scripts/export_crack_stats.py`'s `ADDITIONAL_IMAGES`, with the old undersized file
removed from `data/raw/` entirely so a future naive re-glob can't pick it up again). Its
`image_width_px`/`image_height_px` (7263 / 7544) now fall within the same range as every other row,
and the previous open question about whether the µm calibration factor applies to an
oddly-undersized frame no longer applies — this row uses a standard-sized mosaic capture like the
rest.

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
