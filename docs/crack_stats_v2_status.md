# Crack-stats v2 re-run: status

Running account of this specific effort -- redoing `crack_stats.xlsx` for a scoped batch now
that flaking exclusion and correlation-based corner-artifact pruning both exist in stage 2.
`outputs/` is gitignored, so this doc is the only place that survives across sessions/worktrees
-- keep it updated as work progresses, don't let the checklist below drift from reality.

Separate from [`docs/crack_stats_schema.md`](crack_stats_schema.md) (documents the *existing,
completed* 39-row workbook's columns) and [`docs/calibration_notes.md`](calibration_notes.md)
(the source of truth for *why* each constant has its value -- this doc points there rather
than duplicating).

## Goal

Redo crack stats now that two things are new in stage 2 since the last full export
(2026-07-20):

- Flaking/delamination exclusion (`src/crackgraph/flaking.py`) -- commits `fb03f1b`,
  `e1a8c16`, `594bfe1`, `a1e3e03`.
- Correlation-based corner-artifact pruning (`src/crackgraph/skeleton.py`,
  `CORR_THRESHOLD`) -- commit `1be3da6`.

## Scope: 19-image batch

Three groups (19 images total, not 18 -- an earlier off-by-one error in this doc confused "18 remaining after the pilot" with "18 total"; corrected here), resolved from an initial ambiguous request via direct clarification with the
user:

1. **T2/T3/T4 solvent-ratio, membrane, high gap-height** (6 files): `T2-A_membran_v1/v2`,
   `T3-M_v1/v2`, `T4-M_v1/v2`. T2 has no gap-height variant at all (included as-is, confirmed
   with user). For T3/T4, "high gap-height" = the **unlabeled** file (not the `_H95` variant)
   -- confirmed with user, not inferred.
2. **T5 dew-point, membrane** (5 files, not 6): `0RH_NR212_v1/v2`, `23RH_NR212_v1/v2`,
   `75RH_NR212_v1`. `75RH_NR212_v2` is user-flagged "weird" and excluded -- see memory
   `crack-stats-batch-exclusions.md`, reason not further detailed. Note: despite the "T5"
   framing in the original request, these are the `RH`-named files (`humidity_loading/`), not
   the `T5-M_H*` files -- confirmed directly with the user after an initial wrong assumption.
3. **T5 gap-height, PTFE** (8 files): `T5-PTFE_H50/H95/H145/H190`, each `v1`/`v2`.

All from the `_mm000001.jpg` capture tag. `lu`/`ro` variants for the same layers were raised
as a follow-up idea for later exploration -- explicitly deferred, not part of this batch.

## Open validation concern -- not yet resolved

`CORR_THRESHOLD = 0.99` was tuned by visual sweep (0.8/0.9/0.95/0.99 compared) on a single
image, `T2-A_membran_v2`. That same image's own binarization sanity check **fails**: 27.97%
foreground fraction measured vs. an expected 1-15% band. Two live possibilities, not yet
distinguished: (a) this sample genuinely has unusually high crack density, or (b) something
about thresholding on this specific image is off in a way that could also have distorted the
correlation-threshold tuning. Whoever picks this up next should treat the 0.99 threshold as
**not yet validated to generalize** across the batch's other 17 images -- spot-check a few
before trusting the numbers, don't assume it transfers.

## Methodology, per image, in order

1. Load image, Otsu-binarize (`binarize()`), sanity-check foreground fraction against the
   expected 1-15% band (informational -- doesn't block the run).
2. Scout pass: `skeletonize_and_prune()` on the raw mask -- produces a throwaway skeleton
   whose only surviving output is `reference_width_px` (median `2*medial_radius` sampled at
   surviving skeleton pixels).
3. Flaking identification (`identify_candidates`): pixels wider than
   `WIDTH_FLAG_MULTIPLIER_K x reference_width_px` (K=4.0), connected components >=
   `MIN_CANDIDATE_AREA_PX2` (500) kept as candidates.
4. Grow each candidate back to its true boundary (`grow_and_exclude`, mask-constrained
   dilation, budget `GROWTH_MULTIPLIER x reference_width_px`, GROWTH_MULTIPLIER=2.2) ->
   `excluded_mask`, subtract from the mask -> `mask_corrected`.
5. Real pass: `skeletonize_and_prune()` on `mask_corrected` -- iterative loop pruning (a)
   short spurs/fragments (`branch_type` 1/0, length < `SPUR_PX_PLACEHOLDER`=15px) and (b)
   corner-tracing artifacts (width-vs-position Pearson correlation > `CORR_THRESHOLD`=0.99,
   branches >= `MIN_LEN_FOR_CORR_PX`=4px only, and only ones the length check didn't already
   catch) -- to convergence or `max_iters`=10.
6. `extract_graph()` (skan summarize + node degrees) on the final skeleton.
7. `cut_adjacent_path_indices`: edges whose path comes within
   `CUT_ADJACENT_BUFFER_WIDTH_MULTIPLIER x reference_width_px` (1.0x) of `excluded_mask` at
   any point -- flagged, dropped from length/width stats, kept in the connectivity graph.
8. Compute stats (`crack_area_pct`, `avg_width_px`, `avg_edge_length_px`, `n_components`,
   `giant_component_fraction`, flaking/corner-artifact counts) -- one row.
9. Render `overlay.png` (final skeleton + excluded regions + cut-adjacent edges over the
   original image) and write the cache files (see below).

For *why* each named constant has its specific value, see `CALIBRATION.md` /
`docs/calibration_notes.md` -- not re-explained here.

## Timing / bottleneck findings

Measured on `T2-A_membran_v2` before touching anything, per-stage, rather than guessing:

| stage | before | after EDT fix |
|---|---|---|
| load_image | 0.97s | -- |
| binarize | 0.87s | -- |
| scout `skeletonize_and_prune` | 36.3s | 36.9s |
| exclude_flaking_regions | 2.56s | 2.55s |
| real `skeletonize_and_prune` | 21.8s | 21.4s |
| extract_graph | 0.01s | -- |
| **cut_adjacent_path_indices** | **243.5s** | **6.7s** |
| networkx components | 0.01s | -- |
| **TOTAL** | **306.1s** | **69.4s** |

**What was originally suspected vs. what was actually true**: the corner-artifact correlation
check (built earlier this session, the original suspect for "this might be slow") cost 0.12s
combined across both passes -- negligible. The two optimizations planned for it (disable on
scout pass, pre-filter by length before the per-branch loop) were **not implemented** -- they'd
save nothing measurable, and this effort's own principle is not to add complexity that doesn't
matter.

**What was actually slow**: `cut_adjacent_path_indices`, 80% of the total run. Drilled further:
241.8s of that was one line, `binary_dilation(excluded_mask, footprint=disk(~47px))`, applied
to the full ~7250x7600px (55M-pixel) image -- large-footprint morphological dilation at that
resolution is expensive. The per-edge Python loop in the same function cost 0.06s, not the
problem. A bounding-box crop of the dilation was tried first and only helped ~17% (this
image's 6 flaking candidates are scattered across most of the frame, not clustered, so one
global crop barely shrinks).

**Fix applied** (`src/crackgraph/flaking.py`, `cut_adjacent_path_indices`): replaced the
dilation with `distance_transform_edt(~excluded_mask) <= buffer_px_int` -- "within radius R of
excluded_mask" is exactly what a disk-footprint dilation computes too, but EDT is
algorithmically much faster at this resolution. Verified **byte-identical** output first (100%
pixel-matching mask, same 76 flagged edges) before accepting the speed win as real rather than
an approximation. Result: 6.6s, 37x faster, zero behavior change.

**Net**: 306.1s -> 69.4s per image (4.4x), all downstream numbers identical (1450 edges, 41
components, 6 flaking candidates, 76 cut-adjacent, 84 corner-artifacts pruned -- unchanged).
At ~69s/image, the 19-image batch is roughly ~21 minutes total.

**Deferred, not abandoned** at the time (revisited below once hole-filling + cache/overlay
existed): `skeletonize`'s `method='lee'` vs default `'zhang'` timing comparison; downsampling
the scout pass; a non-iterative single-pass scout prune. Bounding-box pre-filtering
`cut_adjacent_path_indices` was already moot -- that function was already fast.

### Second pass: full re-run with hole-filling, caching, and overlay rendering included

The numbers above stopped at the analysis stage -- they never measured `HOLE_AREA_THRESHOLD_PX2`
(didn't exist yet), `save_analysis_cache`, or `render_crack_stats_overlay`, all now a
permanent part of every image's run. Re-timed the same image, current code, full breakdown:

| stage | time (s) |
|---|---|
| load_image | 0.99 |
| binarize | 0.86 |
| **scout skeletonize_and_prune** | **38.05** |
| &nbsp;&nbsp;remove_small_objects | 0.80 |
| &nbsp;&nbsp;remove_small_holes | 1.00 |
| &nbsp;&nbsp;**skeletonize()** | **22.83** |
| &nbsp;&nbsp;prune loop (skan summarize/prune_paths, corner-artifact check) | 13.41 |
| exclude_flaking_regions | 2.77 |
| **real skeletonize_and_prune** | **22.83** |
| &nbsp;&nbsp;remove_small_objects | 0.83 |
| &nbsp;&nbsp;remove_small_holes | 0.81 |
| &nbsp;&nbsp;skeletonize() | 9.98 |
| &nbsp;&nbsp;prune loop | 11.21 |
| extract_graph | 0.01 |
| cut_adjacent_path_indices | 6.68 |
| stats + networkx | 0.05 |
| save_analysis_cache (6 files) | 0.81 |
| render_crack_stats_overlay (with grid) | 3.54 |
| **TOTAL** | **76.58** |

Stats matched the prior real run exactly (crack_area_pct 26.32%, n_components 35, etc.) --
confirms the re-run is correct, not just fast/slow.

**What this settles**: hole-filling is cheap (~1.0s scout, ~0.8s real -- one more vectorized
skimage call, not a loop, exactly as expected). Cache-writing is cheap (0.81s for all 6
compressed files -- boolean arrays that are mostly False/0 compress well). Overlay rendering
is moderate but not dominant (3.54s for ~1400 edges plus grid annotations). None of these are
worth optimizing further right now -- inventing a fix for a cost that isn't real would just be
added complexity for no benefit.

**What's now the actual bottleneck**: `skeletonize()` itself, 22.83s (scout) + 9.98s (real) =
32.8s, ~43% of the total 76.6s -- by far the single largest identifiable cost. The scout
pass's copy alone (22.83s) is nearly 30% of the *entire* pipeline, spent purely to extract one
number (`reference_width_px`) from a skeleton that's discarded right after. Second largest:
the prune-loop remainder (13.41s scout + 11.21s real = 24.6s, ~32%) -- this is skan's own
`summarize()`/`Skeleton` construction and `prune_paths()` machinery, confirmed (via the
earlier corner-artifact sub-timing, which measured ~0.1s total) to NOT be the corner-artifact
correlation check -- that's still negligible, folded into this remainder but not responsible
for it.

Together, `skeletonize()` + the prune-loop remainder are ~75% of total runtime, and both are
core, load-bearing operations (thinning algorithm, graph construction), not free wins like the
EDT swap was. The scout pass's disproportionate skeletonize() cost (22.83s to extract one
median-width statistic) is now the most concrete, evidence-backed lead for further
optimization -- worth actually investigating (downsampled scout mask, or a non-skeleton width
estimate) as a follow-up, not attempted in this pass since it wasn't asked for yet and needs
its own correctness verification (does a cheaper method change `reference_width_px` enough to
matter downstream?) before being trusted.

## Caching design

See `src/crackgraph/cache_io.py` and the plan file this effort was built from
(`.claude/plans/ok-i-want-to-sunny-taco.md` at the time of writing, worktree-local -- if that
path no longer resolves, this section is the durable summary). Per image, under
`outputs/crack_stats_v2/<image_stem>/`:

- `stats.json` -- exactly the dict `compute_row()` returns.
- `mask_corrected.npz`, `skeleton_final.npz`, `excluded_mask.npz` -- boolean arrays.
- `flaking_candidates.json` -- candidate list + reference width + excluded-area stats.
- `pruned_branches.npz` -- every pruned branch's reason (`spur`/`fragment`/`corner_artifact`),
  length, and full pixel path (indptr/coords-flat format, mirroring skan's own convention),
  so a "what got cut and why" diagnostic image can be regenerated later without recomputing.
- `overlay.png` -- rendered separately (`overlay.render_crack_stats_overlay`), needs the RGB
  source image which isn't part of the cache itself.

`medial_radius` is deliberately not cached (large, cheap to regenerate from `mask_corrected`
via a single `distance_transform_edt` call).

## Status

- [x] Timing baseline measured
- [x] `cut_adjacent_path_indices` EDT fix applied and verified (uncommitted as of writing)
- [x] `skeleton.py`: `PrunedBranchRecord` + `pruned_branches` field added
- [x] `src/crackgraph/cache_io.py`: `save_analysis_cache` / `load_analysis_cache`
- [x] `overlay.py`: `render_crack_stats_overlay()`
- [x] `export_crack_stats.py`: `compute_row()` gains `cache_dir`, `main()` gains `--cache-dir`
- [x] This status doc
- [x] Single-image pilot run (real files on disk, `T2-A_membran_v2`) -- 73.4s total (in line
      with the 69.4s stage-timing estimate plus overlay rendering + cache writing). All 7
      files present with sane sizes (mask/skeleton/excluded-mask arrays ~68KB-678KB compressed,
      `pruned_branches.npz` 15KB for 183 records, `overlay.png` 3.5MB). Cache round-tripped
      correctly against real data (84 corner_artifact + 54 fragment + 45 spur = 183, matching
      the stats.json count exactly). Overlay visually confirmed against this session's earlier
      prototype-script renders of the same image.
- [x] Grid-square overlay (`grid_cell_px` param, spreadsheet-style A1/B2 labels) and
      `HOLE_AREA_THRESHOLD_PX2` (small-hole-filling before both skeletonize passes) added
      after the user reviewed the first pilot overlay and (a) wanted labeled squares instead
      of raw pixel gridlines to point things out verbally, and (b) correctly noticed small
      black specks weren't being cleaned up before the real skeletonize pass -- confirmed by
      grep that `remove_small_holes` was never wired into `src/`, only used in earlier
      throwaway prototype scripts. Re-ran the full pipeline on `T2-A_membran_v2` with the fix:
      real, non-trivial changes, not cosmetic -- `n_components` 41->35, `avg_edge_length_px`
      228.9->249.9 (+9%), `flaking_n_edges_excluded_near_cut` 76->40 (nearly halved),
      `n_corner_artifacts_pruned` 84->89. `crack_area_pct` barely moved (26.33%->26.32%).
      This confirms the fix matters and wasn't just a cosmetic no-op on this image -- worth
      re-checking on other images in the batch, not assuming it's always this small.
- [x] Full 19-image batch run, current code (hole-fill fix + EDT fix + grid overlay
      included) -- 19/19 succeeded, 0 crashes, 991.9s (16.5 min) total wall-clock, well under
      the ~24 min estimate (per-image time varied a lot more than the single-image estimate
      suggested: 21.3s to 106.5s, driven mostly by how much foreground each image actually
      has to skeletonize, not a fixed cost). `outputs/crack_stats_v2/crack_stats.xlsx` has all
      19 rows; each per-image folder has all 8 files (6 cache files + `overlay.png` +
      `overlay_grid.png`). 3 stats.json files spot-checked against the xlsx, exact match.

      **Sanity-check finding, not yet resolved**: 10 of 19 images (>half) failed the
      binarization sanity check (expected foreground fraction 1-15%) --

      | pattern | images | foreground fraction |
      |---|---|---|
      | high (all of T2/T3/T4 solvent-ratio membrane) | T2-A_membran v1/v2, T3-M v1/v2, T4-M v1/v2 | 22.8%-28.0% |
      | high (T5 highest gap height) | T5-PTFE_H190 v1/v2 | 28.6%-29.4% |
      | near-zero | T5-PTFE_H50 v1/v2 | 0.04%-0.13% |
      | passing | all 5 dew-point (RH) images, T5-PTFE_H95 v1/v2, T5-PTFE_H145 v1/v2 | 1.45%-14.5% |

      This directly amplifies the open validation concern above (T2-A_membran_v2, the
      CORR_THRESHOLD calibration image, was already known to fail this check) -- it is not an
      isolated anomaly, it's a systematic pattern affecting the majority of this specific
      scoped batch. Two different situations, not one:
      - The "high" cluster (T2/T3/T4 membrane, T5-PTFE_H190) is plausibly a **real physical
        effect**: solvent-ratio and gap-height are exactly the variables this batch was
        deliberately chosen to vary, so a wider real range of crack density than the
        historical 1-15% band (calibrated against the original, differently-composed 39-image
        dataset) is a believable, not alarming, explanation -- not yet confirmed, just
        plausible.
      - The near-zero `T5-PTFE_H50` pair is a different, more concerning case: 0.02-0.13% is
        close enough to "no crack detected at all" that it's worth a direct visual check
        (open the raw image, or the `overlay.png`) to confirm it's genuinely an
        almost-uncracked sample and not an Otsu threshold failure on that specific image
        before trusting the number.
      - Notable, unprompted side observation from the same run: `T5-PTFE_H95`
        (`giant_component_fraction` ~0.011, `n_components` ~1500-2000) is extremely
        fragmented compared to every other image (`giant_component_fraction` mostly >0.97) --
        combined with `T5-PTFE_H50`'s low-but-less-extreme fragmentation (0.03-0.17) and
        `H145`/`H190`'s near-fully-connected networks (0.75-0.98), the gap-height series shows
        what looks like a percolation-transition-shaped trend (H50 -> H95 -> H145 -> H190
        going from fragmented to fully connected) -- `[interpreted]`, not yet verified as a
        real trend rather than two-samples-per-condition noise, but a real pattern worth
        following up on its own terms, independent of the sanity-check question above.
- [x] Sanity-check pattern above -- partially resolved. User's read: the "high" cluster
      (T2/T3/T4 membrane, T5-PTFE_H190, 22.8%-29.4%) is expected variation, not alarming --
      "some things can have a lot of cracks, that sanity check isn't that good" -- this batch
      was deliberately chosen to vary solvent-ratio/gap-height, and the 1-15% band was never
      calibrated for that. The near-zero `T5-PTFE_H50` pair remains open (not yet visually
      confirmed), though the width divergence noted just below is itself a relevant new data
      point for that question.
- [ ] `lu`/`ro` images -- deferred; `data/cleaned_pics/` (a fuller local mirror of the OneDrive
      source than `data/raw/`) has `lu`/`mm`/`ro` triples for 17 of the 19 samples already
      copied into `data/raw/` (missing for `T5-PTFE_H50_v1` only -- confirmed against the
      original OneDrive source directly, not just the local copy: that replicate's capture
      session never included `lu`/`ro` at all, no `v3` exists to substitute). Not copied into
      `data/raw/` or run yet -- separate future step, user's explicit direction.
- [x] `median_width_px`/`median_width_um` (true per-pixel distance-transform width) and
      `crack_area_pct_excl_flakes` (crack-area density excluding the flaking-exclusion region
      from the denominator) added to `scripts/export_crack_stats.py` -- see
      `docs/crack_stats_schema.md` columns 18-20 for the exact formulas. Both are wired into
      the live `compute_row()` path (future runs get them automatically) and were also
      retroactively backfilled into all 19 already-cached `stats.json` files (and
      `crack_stats.xlsx` regenerated) **without re-running binarize/skeletonize/flaking**,
      confirming the caching design's own stated purpose -- only `skan.Skeleton` +
      `extract_graph` + `cut_adjacent_path_indices` were reconstructed from the cached
      `mask_corrected.npz`/`skeleton_final.npz`/`excluded_mask.npz` arrays, plus one
      `distance_transform_edt` call. Took 369.5s for all 19 (~19s/image on average) -- slower
      than the "low tens of seconds total" estimate in the plan, because graph
      reconstruction (`skan.summarize()` + the per-edge `cut_adjacent_path_indices` loop) on
      these full-resolution images is itself non-trivial, not because anything expensive was
      accidentally re-run.

      `median_width_px` reuses `avg_width_px`'s existing cut-adjacent edge exclusion (not a
      new buffer rule), so the two are directly comparable. Across all 19 images they agree
      to a median 7.0% / mean 8.5% absolute relative difference -- close to the historical
      ~6.6% figure from the old 39-image set, but with real spread: most images sit in the
      1-15% range (both directions -- `median_width_px` reads higher on the RH/humidity and
      T3/T4 images, lower on the T5-PTFE gap-height images), except:
      - **`T5-PTFE_H50_v1`/`v2`**: -27.6% / -27.5% -- by far the largest divergence in the
        batch, `median_width_px` reading well below `avg_width_px` (5.66px/4.47px vs.
        7.81px/6.16px). This is the same near-zero-foreground pair already flagged as an open
        sanity-check concern above -- a network this sparse (0.02%-0.13% foreground) is
        exactly where a global area/length ratio and a true per-pixel median would be
        expected to diverge most (few edges, so the ratio has little averaging to smooth over
        outlier-width pixels/junction blobs) -- `[interpreted]`, reported as a relevant new
        data point for that still-open question, not a resolution of it on its own.

      `crack_area_pct_excl_flakes` differs from `crack_area_pct` only on images with a nonzero
      flaking exclusion (9 of 19) -- by construction, since the two formulas are identical
      when `flaking_excluded_area_pct` is 0. Largest correction: `T5-PTFE_H190_v2` at +4.2%
      relative (24.56% -> 25.59%), then `T2-A_membran_v2` at +1.7% (26.32% -> 26.76%); the
      rest are under 2%.

- [x] **Thesis-notation redirect**: the user supplied final thesis write-up text (Methods +
      Table __) defining 8 statistics under new short names (`crack`, `flaking`, `wcrack`, `N`,
      `fgc`, `ledge`, `ledge,gc`, `dgc`) and asked whether these could be derived from the
      existing 19-image cache with **no new image analysis**. Checked each one against what's
      already stored/derivable:

      | thesis name | source | status |
      |---|---|---|
      | `crack` (%) | `crack_area_pct_excl_flakes` | **real methodology correction, not a rename** -- denominator excludes the flaking-excluded area (legacy `crack_area_pct`, still present unrenamed in the internal spreadsheet, divides by the whole image instead). Already computed correctly and cached; only the doc wording describing it was wrong, corrected here. |
      | `flaking` (%) | `flaking_excluded_area_pct` | already cached, direct rename -- no formula change |
      | `wcrack` (µm) | `median_width_um` | **real methodology correction, not a rename** -- a true per-pixel median (legacy `avg_width_px` is a single global `crack_area / skeleton_length` ratio, not a median or a per-pixel measurement of anything). Excludes cut-adjacent (flaking-cut-truncated) edges, same as the legacy width/length stats -- an implementation detail the thesis prose doesn't spell out, flagged here explicitly. Already computed correctly and cached; only the doc wording was wrong. |
      | `N` (-) | `n_components` | already cached, direct rename -- never touched by any edit this project has made |
      | `fgc` (-) | `giant_component_fraction` | already cached, direct rename -- the underlying code was refactored this session (extracted into `giant_component_nodes()`), but verified bit-for-bit identical to the original formula on every image checked, so this is still a true no-op, not a hidden formula change |
      | `ledge` (µm) | new: median (not `avg_edge_length_px`'s mean) edge length, whole image | new formula, cache-derivable |
      | `ledge,gc` (µm) | new: same median, restricted to giant-component edges | new formula, cache-derivable |
      | `dgc` (µm) | new: straight-line span between the giant component's two farthest points, sampled from every skeleton pixel in the component (not just its junction/endpoint nodes) | new formula, cache-derivable -- see the dedicated entry below for why node coordinates alone weren't enough |

      All 8 confirmed derivable from `mask_corrected.npz`/`skeleton_final.npz`/`excluded_mask.npz`
      alone -- no re-run of binarize/skeletonize/flaking-correction needed for any of them.

      Implementation: added `median_edge_length_px()`, `giant_component_nodes()` (refactored out
      of the existing `giant_component_fraction` block so both use the identical "giant by summed
      length, not node count" definition), and `giant_component_span_px()` (convex-hull-reduced
      diameter, with a brute-force fallback for exactly-collinear point sets, which a straight
      single-crack giant component produces and which makes `scipy.spatial.ConvexHull` raise) to
      `scripts/export_crack_stats.py` -- see `docs/crack_stats_schema.md` columns 21-26. Wired
      into the live `compute_row()` (future runs get these automatically) and backfilled onto all
      19 cached images the same way as the previous retrofit, 119.6s total this time (cache was
      already warm from the previous backfill, so no `distance_transform_edt` recompute was
      needed for these three -- only graph reconstruction). 6 new unit tests added (median vs.
      mean distinction, cut-adjacent exclusion, node-filter isolation, giant-component-by-length
      selection, known-diagonal span, collinear-fallback span) -- full suite 114/114 passing.

      **New deliverable**: `outputs/crack_stats_v2/thesis_stats.xlsx` -- 19 rows, exactly the 8
      renamed columns above plus `image_filename`/`source_folder` for reference. Separate file
      from the internal `crack_stats.xlsx` (which keeps every column, thesis-named or not) per
      the user's explicit request, not a replacement for it.

      **Genuine new edge case surfaced, not a bug**: `T5-PTFE_H50_v2`'s `dgc` is `NaN` -- its
      giant component turned out to be a single closed crack loop with no junctions at all, which
      skan represents as one node with a self-loop edge. "Distance between the two farthest
      nodes" isn't defined for one node, so `NaN` is the honest answer, not a fabricated 0 or the
      loop's own perimeter (a different question). Documented in the schema doc caveats.

      **Sanity-check cross-reference**: the new `N`/`fgc` values read exactly as the thesis
      text's own worked interpretation predicts -- `T5-PTFE_H95` (`fgc` ~0.011, `N` ~1500-2000)
      matches "many similarly sized individual cracks" (§ thesis text, `N` near `1/fgc` when
      `fgc` << 0.5), while `T4-M`/`T3-M`/`T2-A_membran` (`fgc` > 0.97) match "one large
      interconnected network." Not new evidence on its own (these are renamed existing numbers),
      but confirms the renamed/re-derived values are behaving sensibly against the thesis
      text's own qualitative description before handing the sheet over.

- [x] **Follow-up: `crack`/`wcrack` doc wording corrected, `dgc`'s NaN case fixed**. User pushback
      on the entry above, verified rather than just addressed by rewording:

      1. **"`crack`/`wcrack`: already cached, direct rename" was misleading.** Both are real
         methodology corrections over their legacy counterparts (`crack` excludes the flaking area
         from the denominator, `wcrack` is a true per-pixel median vs. a global ratio) -- the
         mapping table above is now reworded to say so explicitly. The already-reported numbers
         were correct throughout; only the description was wrong. Checked `N`/`fgc` too, on the
         same suspicion -- these two genuinely are exact, unchanged carryovers (verified
         bit-for-bit identical between the old inline formula, the refactored
         `giant_component_nodes()`-based formula, and the stored value, on 4 real images including
         `T5-PTFE_H50_v2`) -- no wording fix needed there.

      2. **Found, and closed, a real (but harmless) cache-reconstruction gap**: `mask_corrected.npz`
         caches the *input* to the second (real) `skeletonize_and_prune` call, not its *output*
         (`skeleton_result.mask_clean`, after that call's own despeckling runs again) -- so
         `median_width_px` recomputed from cache wasn't using a byte-exact reconstruction of what
         the live pipeline actually measured width from. Measured the real difference (6 of 14.3M
         pixels on `T2-A_membran_v1`, 0 on two other images checked) and confirmed it changed the
         reported `median_width_px` by exactly zero (bit-for-bit identical, `31.04834939252005`
         either way) -- the median doesn't move when six stray filled-in specks don't land on a
         sampled skeleton pixel. Still fixed for real (re-despeckle `mask_corrected` with the same
         `remove_small_objects`/`remove_small_holes` calls `skeleton.py` uses before computing
         `medial_radius`) rather than left as an unverified "probably fine."

      3. **`dgc`'s `NaN` on `T5-PTFE_H50_v2` was a real modeling gap, not a data-availability
         problem.** `giant_component_span_px` only received the giant component's sparse
         junction/endpoint node coordinates; that component turned out to be a single closed crack
         loop with no junctions at all (skan represents it as one node with a self-loop edge), so
         a span between "two farthest nodes" was undefined for a 1-point set. The user asked why
         this wasn't just `0` -- checked the loop's actual pixel path first: 312 points, a real
         closed ring spanning a ~107x108px bounding box, not a 1-2 pixel artifact, so `0` would
         have been a false "no spatial extent" claim, not a cautious one. **Fix**: the span is now
         sampled from every skeleton pixel on every edge inside the giant component (via
         `skel.path_coordinates`), not just its node coordinates -- `giant_component_span_px()`
         itself needed no change, only what gets passed into it. Tested against all 19 images
         before committing to the fix (not just the one broken row):

        | image | dgc before (um) | dgc after (um) |
        |---|---|---|
        | `T5-PTFE_H50_v2` | NaN | 70.27 |
        | `T5-PTFE_H190_v1` | 6369.81 | 6407.78 (+0.6%) |
        | `T5-PTFE_H190_v2` | 6380.28 | 6404.90 (+0.4%) |
        | `T3-M_v2` | 6348.39 | 6377.22 (+0.5%) |
        | `T3-M_v1` | 6323.35 | 6332.55 (+0.1%) |
        | `T2-A_membran_v1` | 6422.76 | 6423.18 (+0.01%) |
        | remaining 13 of 19 | -- | unchanged |

         Confirms the "pixel cloud is a superset of the node set, so the new value can only be
         >= the old one" prediction held on every real image -- the fix generalizes, it isn't a
         patch for one row. Added a regression test
         (`test_giant_component_span_handles_a_closed_loop_with_no_junctions`) using a synthetic
         rectangular-ring mask, confirmed to reproduce the exact same single-self-loop topology as
         the real `T5-PTFE_H50_v2` case before asserting on it.

      Re-ran the cache-only backfill with both fixes (2 and 3) applied -- 384.3s for all 19 images
      (no re-run of binarize/skeletonize/flaking), `thesis_stats.xlsx`/`crack_stats.xlsx`
      regenerated. Net effect on the actual spreadsheet the user cares about: `crack`, `flaking`,
      `wcrack`, `N`, `fgc`, `ledge`, `ledge_gc` unchanged on all 19 rows; `dgc` changed on exactly
      the 6 rows in the table above.
