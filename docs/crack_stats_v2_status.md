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

## Scope: 18-image batch

Three groups, resolved from an initial ambiguous request via direct clarification with the
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
At ~69s/image, the 18-image batch is roughly ~21 minutes total.

**Deferred, not abandoned** (only worth revisiting if ~21 min turns out to be too slow in
practice): `skeletonize`'s `method='lee'` vs default `'zhang'` timing comparison; downsampling
the scout pass (needs verifying `reference_width_px` doesn't shift meaningfully first); a
non-iterative single-pass scout prune. Bounding-box pre-filtering `cut_adjacent_path_indices`
is now moot -- that function is already fast.

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
- [ ] Single-image pilot run (real files on disk, `T2-A_membran_v2`) -- next
- [ ] Full 18-image batch -- deliberately not started, separate step after the pilot is
      confirmed good
