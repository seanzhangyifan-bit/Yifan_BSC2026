# crack_stats_v3 status

Running account of this effort. Distinct from `docs/crack_stats_v2_status.md`, which is an
unrelated project: a re-run of today's two-pass flaking methodology over a different image
batch plus a thesis-notation mapping layer, not a methodology change. "v2" was already taken
by that effort, hence "v3" here, even though nothing called "v1"/"v2" preceded this
methodologically -- `scripts/export_crack_stats.py` is what's referred to as "v1" below,
purely for contrast.

## What this is

A second, independent implementation of the crack-stats export
(`scripts/export_crack_stats_v3.py`), alongside `scripts/export_crack_stats.py`, not replacing
it. Both remain runnable; nothing in the existing pipeline (`export_crack_stats.py`,
`flaking.py`'s existing functions, `skeleton.py`, `cache_io.py`, `overlay.py`,
`docs/crack_stats_schema.md`, `docs/crack_stats_v2_status.md`) was modified.

## Why

v1 excludes a flaked/delaminated region by: scout-skeletonizing once to get a reference crack
width, growing a detected flake back to its true boundary (mask-constrained dilation, budget
2.2x reference width), subtracting it from the mask, and skeletonizing a **second time** on
the corrected mask. Edges that still end up within 1.0x reference-width of the flake boundary
(`flaking.cut_adjacent_path_indices`, a distance-transform buffer test) get dropped from
length/width stats but are deliberately **kept** in the connectivity graph `G` -- in that
two-pass design they're real truncated stubs at an actual mask boundary, so component
membership through them is real topology even though their own length isn't trustworthy.

A simpler procedure was proposed (matching a methodology write-up the user drafted): skip the
second skeletonize pass, and instead of a distance buffer, omit any edge/node with **any
pixel physically inside the grown-out flake** -- no separate margin. A naive port of this
would corrupt the connectivity stats (`n_components`, `giant_component_fraction`,
`giant_component_span_um`, `median_edge_length_gc_um`): a delaminated blob's own
un-corrected skeleton is inherently multi-branched, and its junction-to-junction edges are
structurally un-prunable by `skeletonize_and_prune`'s spur/fragment pruning (see `flaking.py`'s
and `skeleton.py`'s module docstrings) -- if left in the connectivity graph, they would falsely
bridge two real crack networks that only "connect" through a region we have zero evidence
about.

v3 fixes this by filtering the omitted edges out of `G` itself (and everything derived from
it), not just out of the per-edge stat columns.

## Methodology (v3)

1. Load, Otsu-binarize (same as v1).
2. **One** `skeletonize_and_prune()` pass on the raw, uncorrected mask -- current defaults
   kept (spur/fragment pruning at <15px, up to 10 iterations, AND the correlation-based
   corner-artifact criterion at `CORR_THRESHOLD=0.99`). The methodology write-up this was
   drafted from doesn't mention the corner-artifact criterion, but that's because it predates
   that addition to the shared pipeline, not a deliberate omission -- v3 uses whatever
   `skeletonize_and_prune` does today, same as v1.
3. `exclude_flaking_regions()` -- identical call to v1's scout-pass step (width >
   4.0x reference width, area >= 500px², grown back by up to 2.2x reference width). Here its
   output is the final answer; no second pass follows. Its `mask_corrected` field is still
   computed as a harmless byproduct (needed for `cache_io` compatibility, see below) but not
   used to build the graph.
4. `extract_graph()` -- one graph. It includes the flaked blob's own interior mesh when
   candidates exist (v1's second pass never generates this, since the region is mask-absent
   by the time it skeletonizes).
5. `flaking.flake_touching_path_indices()` (new, additive function alongside
   `cut_adjacent_path_indices`, which is untouched) -- any edge with at least one pixel inside
   `excluded_mask` is omitted. No `distance_transform_edt`, no `reference_width_px`/buffer
   multiplier -- direct mask membership is the only test.
6. Stats computed with the same formulas as v1, substituting `omitted` for `cut_adjacent`
   everywhere -- except the connectivity block, which needed real changes (not just a
   substitution), detailed below.
7. Optional `--cache-dir`: reuses `cache_io.save_analysis_cache` / `overlay.render_crack_stats_overlay`
   unmodified.

### Why the connectivity block needed more than substitution

- `G` is built from `summary.loc[~summary.index.isin(omitted)]` -- filtered, unlike v1 which
  builds `G` from the full unfiltered summary.
- `full_total_length_px` (the `giant_component_fraction` denominator) is **also** filtered.
  v1 can safely sum its full summary because its `mask_corrected` already physically removed
  the flake before skeletonizing, so no fake mileage exists there. v3's full summary *does*
  contain the blob's own spurious interior mileage when candidates exist -- an unfiltered sum
  would silently deflate the fraction.
- `gc_edge_mask` (feeding `giant_component_span_px`/`median_edge_length_gc_px`) gets an added
  `& ~summary.index.isin(omitted)` term. v1 deliberately omits this filter, since its stub
  edges are real truncated tips whose pixel positions are trustworthy even though their length
  isn't. v3 has no such "trustworthy stub" concept -- an edge is either fully kept or fully
  omitted, so an omitted edge must not contribute pixels even if both its endpoints happen to
  be giant-component members via other, kept paths.

## Disclosed semantic gaps versus v1 (not bugs, not being "fixed")

- **`crack_area_px2` isn't re-cleaned after subtraction.** v1's version comes from a second
  `skeletonize_and_prune` call, so it's re-despeckled (`remove_small_objects`/
  `remove_small_holes`) after the flake is carved out. v3 reuses
  `flaking_result.mask_corrected` (= `mask_clean & ~excluded_mask`) directly, with no
  re-cleaning pass. v1 and v3 area numbers on flaked images are therefore not expected to be
  bit-identical even given the same source image -- confirmed on the real spot-check below,
  where they differ in the 5th significant figure.
- **A `--cache-dir` run's `mask_corrected.npz` means something different than in a v1 cache
  directory.** It's a valid `FlakingResult.mask_corrected` value, but it does **not**
  correspond to what was actually skeletonized to produce that same entry's
  `skeleton_final.npz` -- v3's skeleton comes from the uncorrected mask. Don't point a v3
  `--cache-dir` at an existing v1/v2 cache directory, and don't assume that correspondence
  holds when reading a v3 cache.
- **`n_corner_artifacts_pruned` (and the other `SkeletonResult` pruning-diagnostic fields)
  reflect pruning on the flake-inclusive mask.** The count can mix genuine real-crack
  corner-artifact pruning with however much of the blob's own interior noise got pruned along
  the way -- a real change in what that column means, confirmed on the spot-check below (83
  vs. v1's 89 on the same image).
- **The cached overlay's legend text is v1's wording**, reused verbatim since `overlay.py`
  wasn't modified: "cut-adjacent (dropped from length/width stats)" understates what v3 also
  drops those edges from (the connectivity graph too). Cosmetic only.

## Status

- [x] `flaking.flake_touching_path_indices` added (additive, `cut_adjacent_path_indices`
      untouched).
- [x] `scripts/export_crack_stats_v3.py` written, reusing v1's constants and generic utility
      functions (`median_pixelwise_width_px`, `median_edge_length_px`, `giant_component_nodes`,
      `giant_component_span_px`) by import.
- [x] `tests/test_export_crack_stats_v3.py`: unit tests for `flake_touching_path_indices`
      (membership-based flagging, empty-mask guard, non-overlapping-edge case, empty-summary
      guard) plus a synthetic-mask regression test proving the specific failure mode this
      pipeline exists to avoid -- two real crack-like networks (each with its own T-branch,
      independent of the blob) that a large connecting blob would falsely merge into one
      component if the connectivity graph were built from the unfiltered summary, correctly
      split into two once `flake_touching_path_indices`'s output is filtered out of `G`. All 5
      new tests pass; full existing suite (120 tests) unaffected.
- [x] Single-image spot-check against v1 on `aquivion_t2_membran/T2-A_membran_v2_mm000001.jpg`
      (the same reference image `flaking.py`/`skeleton.py`'s own docstrings use), run to
      completion, `--cache-dir` path exercised, overlay visually inspected:

  | column | v1 | v3 |
  |---|---|---|
  | runtime | 78.3s | 38.7s |
  | crack_area_pct | 26.31607 | 26.31615 |
  | crack_area_mm2 | 5.343065 | 5.343081 |
  | avg_width_um | 28.1643 | 27.8963 |
  | median_width_um | 28.0488 | 27.8626 |
  | median_edge_length_um | 140.883 | 141.556 |
  | n_components | 35 | 32 |
  | giant_component_fraction | 0.98130 | 0.98115 |
  | median_edge_length_gc_um | 142.261 | 142.698 |
  | giant_component_span_um | 6343.013 | 6343.013 |
  | flaking_n_candidates | 6 | 6 |
  | n_edges omitted (name differs) | 40 (near-cut buffer) | 46 (direct membership) |
  | n_corner_artifacts_pruned | 89 | 83 |

  Area/width/length columns agree closely, as expected (both pipelines already drop the same
  near-boundary edges from those). Runtime is ~2x faster, as expected (one fewer full-resolution
  skeletonize+prune pass). `flaking_n_candidates` and `flaking_excluded_area_pct` match exactly,
  as expected (same detection call). `n_components` (35 vs. 32) and the omitted-edge count (40
  vs. 46) differ -- the intended, disclosed effect of the methodology change: v3's single-pass
  graph contains extra edges from the blob's own un-prunable interior mesh that v1's second pass
  never generates, and v1's `cut_adjacent` buffer operates on a differently-shaped
  already-corrected skeleton near the boundary. `giant_component_span_um` matched exactly on
  this image -- the giant component's extremal points evidently sit far from any flaked patch
  here, so this particular column happened not to be sensitive to the methodology difference on
  this image; not a general guarantee.
- [x] Batch B/C/D run (19 images) completed -- see section below.
- [x] Batch D's T2 source corrected (was wrong -- see "T2 source correction" below) and
      re-run with per-stage timing instrumentation added to `compute_row()`.
- [x] v2-vs-v3 comparison on the 13 images the two datasets happen to share -- see "v2-vs-v3
      comparison" section below.
- [ ] No full run across the entire default 39-image `data/raw/` scope yet -- only the
      single-image v1-vs-v3 spot-check and the 19-image B/C/D batch below have been run so far.
- [ ] No cross-image validation of the `n_components` sensitivity noted above -- the existing
      v2 status doc already flagged this same image's `n_components` as sensitive to
      hole-filling (41->35 there); worth keeping in mind that this metric is one of the more
      fragile ones to compare across methodologies, image to image.

## T2 source correction

The first Batch D run (above) used `T2-A_membran_v1/v2` (`data/raw/aquivion_t2_membran/`) as
T2's "low height" counterpart to T3/T4's `_H95` files. This was wrong: `aquivion_t2_membran/`
traces back to a different OneDrive source project ("Pt Kat Aquivion T2") than T3/T4's `_H95`
files ("Pt Kat Characterization 2") -- not a gap-height variant of the same series at all, just
an unrelated T2 capture. The user caught this and pointed at "Pt Kat Characterization 2" in
`all_pics`, which does have its own T2 image (`Light Microscopy/T2-M_H90/`) -- the correct,
consistent counterpart to `T3-M_H95`/`T4-M_H95`.

Copied in (visually confirmed clean of any blue scale bar on both `mm000001` files first):
`data/raw/characterization2_membran/T2-M_H90_v{1,2}_{lu,mm,ro}000001.jpg`. The `v1` source
filenames used an inconsistent `T2-A_M_H90_...` prefix (vs. `v2`'s plain `T2-M_H90_...`) --
normalized to `T2-M_H90_v1_...` on copy, matching `v2` and the sibling `T3-M_H95`/`T4-M_H95`
convention. `scripts/export_crack_stats_v3_batch_bcd.py`'s `BATCH_D_T2_T3_T4_MEMBRANE_H95`
updated accordingly and the full 19-image batch re-run (superseding the old T2 rows entirely,
not just patching them). Notably, `T2-M_H90` has **zero** flaking candidates on both replicates
(the old, wrong `T2-A_membran` had 2 and 6) -- a real, disclosed change from fixing the source,
not a pipeline bug.

## Per-stage timing

`compute_row()` now records wall-clock time (`time.perf_counter()`) for five stages plus an
independently-measured total, added as new `stats_row` columns -- purely additive, no existing
column or behavior changed:

`runtime_binarize_s`, `runtime_skeletonize_s`, `runtime_flaking_s` (`exclude_flaking_regions` +
`flake_touching_path_indices` combined), `runtime_graph_extract_s`, `runtime_stats_s`,
`runtime_total_s` (whole-function wall clock, measured independently -- can exceed the sum of
the five buckets by a small margin: `load_image` and dict assembly aren't separately bucketed).

On the 19-image batch, `runtime_total_s` ranged 28.3s-86.5s (mean ~46s), consistent with the
single-image spot-check above (38.7s on a similar-resolution image). `runtime_skeletonize_s`
dominates every row (typically 70-90% of total) -- matches the earlier profiling note in this
doc's "Second pass" timing table, where `skeletonize()` itself was already the largest single
cost before this pipeline existed.

## Batch B/C/D run (19 images)

Requested as three named groups; two of the three needed direct reconfirmation with the user
rather than reusing a same-sounding prior resolution, because the plain-language names don't
map onto filenames the obvious way (see memory `crack-stats-batch-naming-ambiguity`, and
`docs/crack_stats_v2_status.md`'s own "19-image batch" section, which hit the identical
ambiguity once before with a *different* resolution for one of the two groups):

- **Batch B -- T5 gap-height variation, PTFE** (unambiguous): `T5-PTFE_H50/H95/H145/H190`,
  `v1`/`v2` each, `data/raw/characterization2_ptfe/` -- 8 files.
- **Batch C -- "T5 rel humidity variation on membrane"**: confirmed to mean the `RH`-named
  files in `data/raw/humidity_loading/` (`0RH_NR212`, `23RH_NR212`, `75RH_NR212` -- NR212 is
  the membrane substrate there), not the literally-`T5`-named `T5-M_H190/H95` files in
  `data/raw/T5/`. Same resolution as the prior batch. `75RH_NR212_v2_mm000001.jpg` excluded
  (user-flagged "weird" in a prior session, memory `crack-stats-batch-exclusions`) -- 5 files.
- **Batch D -- "T2, T3, T4 low height on membrane"**: T3/T4 each have an unlabeled membrane
  file and an `_H95` variant; T2 has no `_H95` variant. The prior batch used the unlabeled file
  only (called "high gap-height" there). This time the user explicitly chose the **`_H95`
  variant only** -- the opposite choice, confirmed directly, not an oversight. T2's file was
  initially sourced wrong (`T2-A_membran`, from an unrelated OneDrive project) and corrected to
  `T2-M_H90` from the same "Pt Kat Characterization 2" source as T3/T4 -- see "T2 source
  correction" below -- 6 files: `T2-M_H90_v1/v2`, `T3-M_H95_v1/v2`, `T4-M_H95_v1/v2`.

Run via the new `scripts/export_crack_stats_v3_batch_bcd.py` (hardcodes this exact 19-path
list, grouped/commented by batch, reusing `export_crack_stats_v3.compute_row()` unmodified) --
not a general-purpose CLI flag on `export_crack_stats_v3.py`, since this specific grouping is a
one-off thesis-batch selection. No `--cache-dir` used for this run (xlsx only). Output:
`outputs/crack_stats_v3_batch_bcd.xlsx`, 19 rows, all 33 columns (27 + 6 timing columns, added
after this batch's first run -- see "Per-stage timing" below) populated, zero NaNs.

**Sanity check -- Batch B's own internal trend**: `crack_area_pct` rises essentially
monotonically with gap height across the H50->H190 sweep (0.02% / 0.13% at H50 up to 25-28% at
H190), and `giant_component_fraction` follows the same pattern (0.16/0.03 at H50's two
replicates up to 0.97-0.98 at H190) -- consistent with a percolation transition as coating
thickness (and hence post-drying crack density) increases with Rakelspalt gap. This is a real,
physically-sensible result the pipeline reproduces, not just "ran without crashing."

**Flaking**: zero candidates on every Batch C (RH_NR212, membrane) image -- consistent with
`flaking.py`'s own module docstring noting delamination "seen so far on membrane-substrate
T2/T3/T4", not this humidity series. In Batch D (post-correction), only `T3-M_H95_v2` shows any
flaking (2 candidates); `T2-M_H90` (both replicates) and the rest of T3/T4 show none -- plausible
sample-to-sample variation.

**Other notable finding**: `T2-M_H90` (both replicates) has by far the highest `n_components` in
either batch's dataset -- 14,348 and 12,208, next-highest being T5-PTFE_H95_v1 at 1,994. Flagged
here as a real, measured number worth being aware of, not investigated further this session --
could reflect a genuinely more fragmented crack network at this condition, or be worth a visual
spot-check before relying on it.

No v1 equivalent run exists for this specific 19-image batch (v1's own batches used different
scope/selection, per `docs/crack_stats_v2_status.md`) -- see "v2-vs-v3 comparison" below for a
comparison against a *different* existing dataset that happens to share 13 of these 19 images.

## v2-vs-v3 comparison

`outputs/crack_stats_v2/crack_stats.xlsx` (a different, already-existing effort -- see that
doc's own status file) happens to cover the exact same 13 images as this batch's B (8
`T5-PTFE_H50/95/145/190`) + C (5 `RH_NR212`) groups (batch D has no v2 equivalent -- v2 used the
unlabeled T2/T3/T4 files, not the `_H95` variant). Joined on `image_filename`, compared across 9
headline columns (crack area, avg/median width, median segment length overall and in the giant
component, component count, giant-component fraction and span, flaking-excluded area). Full
results, dumbbell charts per batch, and the complete numeric table published as an HTML report:
https://claude.ai/code/artifact/94529aca-a2a9-4d6f-b24d-459f58a7e690

Headline finding: **all 5 batch C (RH_NR212) images match to 0.0% on every one of the 9
columns** -- these images have zero flaking candidates, so v1/v2's two-pass correction and v3's
single-pass omission have nothing to disagree about. Differences only appear in batch B
(T5-PTFE) images that actually have flaking, and track the disclosed methodology difference
exactly: `crack_area_pct_excl_flakes` and `flaking_excluded_area_pct` still match to
within 0.01% everywhere (same flaking-identification call in both pipelines), while
`n_components`/`giant_component_span_um`/width columns show mean absolute differences of
2-4.5% (max 30-37%, concentrated on `T5-PTFE_H50_v1` and `T5-PTFE_H190_v1/v2` -- the images
with the most flaking, and in `T5-PTFE_H50_v1`'s case also the sparsest crack network, where a
handful of edges reclassifying swings the relative percentage further). This is consistent with
the single-image spot-check above and with the design rationale in this doc's "Why" section --
the differences are exactly where the methodology says they should be, and nowhere else.
