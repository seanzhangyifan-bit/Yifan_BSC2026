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
- [ ] Full-batch run across `data/raw/` not yet performed (single-image spot-check only so
      far) -- worth doing before treating v3's numbers as final for any reported batch.
- [ ] No cross-image validation of the `n_components` sensitivity noted above -- the existing
      v2 status doc already flagged this same image's `n_components` as sensitive to
      hole-filling (41->35 there); worth keeping in mind that this metric is one of the more
      fragile ones to compare across methodologies, image to image.
