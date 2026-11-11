# Code review: the whole `thesis_export/` folder

- **Date**: 2026-11-11
- **Scope**: every file in `thesis_export/`: `src/` (21 modules), `scripts/` (16 scripts), `app.py`,
  `tests/` (20 files), and the top-level docs. `synthetic.py` (test-pattern drawing) and the
  experimental tracing script were skimmed, not read line by line.
- **Baseline**: commit `08d6e83`, plus the uncommitted doc tidy-up in `skeleton.py`,
  `flaking.py`, `CALIBRATION.md`, `METHODOLOGY.md`, `docs/calibration_notes.md` and the new
  `docs/design_notes.md`.
- **Status**: findings 1–11 and 13–16 are fixed or labelled, and R5 is done (see their sections).
  A second pass found three more bugs, 17–19, also fixed. Still open: 12 (evidence labels and
  uncalibrated settings) and readability items R1–R4 and R6. All 157 tests passed on the baseline;
  174 pass after the fixes.

## Summary

The analysis code is careful and honest: every number carries an evidence label, known
limitations are shown rather than hidden, and the tests pass. Most problems are in the
paperwork around the code, not the measurements themselves.

- **2 confirmed bugs that affect results or block use.** The corner cross-check reads a
  west-pointing crack as east-pointing (finding 1), and the batch exporters crash in this folder
  because the image path is hard-coded (finding 2).
- **1 overclaim in the spreadsheets.** Every exported row says its scale bar was "visually
  confirmed", even rows from images nobody checked (finding 3).
- **The docs fell behind the code.** The kink-detection removal, the folder reorganisation and
  later edits left 63 dead file paths, 20 wrong line numbers, and a shipped example that still
  shows the deleted kink feature.
- **Readability**: one 550-line function, several 40–70-line opening docstrings, and settings
  whose explanation sits *below* the line it describes. This is the same issue you flagged in
  `skeleton.py`.

## How to read this

| Severity | Meaning |
|---|---|
| **High** | Changes a reported result, crashes a documented command, or puts an unsupported claim in an output. Fix before results go in the thesis. |
| **Medium** | Misleading docs, slow paths, or rigor gaps a reviewer could raise. Fix before submission. |
| **Low** | Real but rare or cosmetic. Fix when convenient. |

"Verified" means I reproduced it by running code. "From reading" means I found it by reading
the code but didn't run it.

## Findings at a glance

| # | Severity | What | Where |
|---|---|---|---|
| 1 | High | ~~Corner cross-check flips west-pointing cracks to east~~ **Fixed** | `corners.py:205`, `:237` |
| 2 | High | ~~Batch exporters crash: image folder hard-coded, no way to point at your own~~ **Fixed** | `export_crack_stats.py:67–69, 361–365` |
| 3 | High | ~~Every exported row claims "scale bar visually confirmed"~~ **Fixed** | `export_crack_stats.py:309`, `export_crack_stats_v3.py:202` |
| 4 | Medium | ~~v3 definitions sheet describes the v1 method, not v3~~ **Fixed** | `add_definitions_sheet.py:88` |
| 5 | Medium | ~~Docs still describe the deleted kink feature~~ **Fixed** | 4 docs, example gallery, `CALIBRATION.md` |
| 6 | Medium | ~~20 wrong line numbers in the calibration docs; table shows stray backslashes~~ **Fixed** | `CALIBRATION.md`, `docs/calibration_notes.md` |
| 7 | Medium | ~~63 references to file paths that no longer exist~~ **Fixed** | 15 paths, across `src/`, `scripts/`, docs |
| 8 | Medium | ~~Console report names a flaking criterion that was dropped~~ **Fixed** | `analyze_image.py:384` |
| 9 | Medium | ~~Two steps get very slow on a full image~~ **Fixed** | `edge_metrics.py:272`, `corners.py:282` |
| 10 | Medium | GUI shows crack stats and pipeline results for different image regions **(labelled)** | `app.py` |
| 11 | Medium | ~~`--n-rows`/`--n-cols` accepted, but anything other than 2×2 crashes at the end~~ **Fixed** | `overview_figure.py:44–45` |
| 12 | Medium | Three open items from the July review | `junctions.py`, `CALIBRATION.md` |
| 13 | Low | ~~Junction angle fit mixes up both ends of a loop~~ **Fixed** | `junctions.py:163–164` |
| 14 | Low | ~~One validation row always says PASS~~ **Fixed** | `validation_cases.py:323` |
| 15 | Low | ~~Small correctness and consistency nits~~ **Fixed** | various |
| 16 | Low | ~~Entry points with no tests~~ **Fixed** | `analyze_image.py`, `app.py`, v3 `compute_row` |
| 17 | Medium | ~~Connectivity graph drops one of two segments joining the same junctions~~ **Fixed** | `export_crack_stats.py`, `export_crack_stats_v3.py` |
| 18 | Medium | ~~Overview figure skips flaking exclusion~~ **Fixed** | `overview_figure.py` |
| 19 | Low | ~~A crack ordered before itself is dated, not reported as a cycle~~ **Fixed** | `precedence.py` |
| R1–R6 | Readability | Long function, long docstrings, comments under settings, duplicate helpers, dead code | various |

---

## High

### 1. Corner cross-check flips west-pointing cracks to east (verified) — FIXED

> **Fixed 2026-11-11.** Both averages now use `_mean_bearing`, which averages along the shorter
> arc. Two regression tests were added to `tests/test_corners.py`: a direct 179°/−179° check, and an
> end-to-end west-pointing T, which reported −1.4° before the fix and 178.6° after. The rotation sweep
> below went from 10 flipped cases to 0.

**What's wrong.** `corners.py` combines two angle readings by averaging them with a plain
`(a + b) / 2`, at line 205 (T-junctions) and line 237 (Y-junctions). Angles wrap around at ±180°,
so two readings of the *same* west-pointing wall, 179° and −179°, average to **0°, which is
east**. The check just before each average uses a wrap-aware difference, so the pair passes as
"agreeing" first.

**Evidence.** I ran synthetic T-junctions with the abutter pointing 176–184° (about west), with
and without pixel jitter. In 9 of 20 runs, the corner method reported the abutter at about 0°.
It still labelled the junction "T" and still reported it as agreeing with the tangent fit. One
Y-junction near west flipped to "ambiguous", a false disagreement. The clean, unrotated test
cases never hit this, which is why the test suite passes.

**Why it matters.**
- The corner method's "agree / disagree" counts, which `METHODOLOGY.md` treats as a validation
  signal, are unreliable for cracks running roughly east–west.
- In `precedence.py`, a flipped corner reading can't be matched to any skeleton arm, so the
  junction loses its corner-method support. It ends up counted as "corner-resolved T not mapped"
  instead of "both methods agree". No wrong precedence arc is created, but the agreement
  statistics are understated, and only for one orientation.

**Fix.** Average angles on the circle. Either add half the wrapped difference
(`a + _angle_diff(b, a) / 2`), or average unit vectors and take `atan2`. Add a regression test
with an abutter at 179°/−179°. This is a ~5-line change.

### 2. Batch exporters can't find images in this folder (verified) — FIXED

> **Fixed 2026-11-11.** All four scripts with a hard-coded image folder (`export_crack_stats.py`,
> `export_crack_stats_v3.py`, `export_crack_stats_v3_batch_bcd.py`, `skeleton_loop_sweep.py`) take
> `--data-dir`. Missing `ADDITIONAL_IMAGES` entries are skipped with a notice, and the "no images"
> check runs after filtering. The batch B/C/D runner lists any missing files up front. On
> `../data/raw`, the new discovery picks exactly the same 41 images as the old code.

**What's wrong.** `export_crack_stats.py` and `export_crack_stats_v3.py` look for images at a
fixed location, `<thesis_export>/data/raw/**/*_mm000001.jpg`, and have no option to point them
anywhere else. `thesis_export/data/` doesn't exist, since `README.md` says the images are
deliberately not bundled. The "no images found" safety check (line 365) never triggers, because
one extra hard-coded image (`ADDITIONAL_IMAGES`, line 67) is always added to the list. So the
script crashes with `FileNotFoundError` on that one file. `export_crack_stats_v3_batch_bcd.py`
and `scripts/validation/skeleton_loop_sweep.py` have the same hard-coded root.

**Why it matters.** `README.md` says "Point any script at your own images instead", but the
documented command for deliverable #2 can't run from the submitted folder at all. The GUI isn't
affected, because it calls `compute_row` on uploaded files directly.

**Fix.**
- Add a `--data-dir` option (default: `data/raw` next to the repo).
- Only add `ADDITIONAL_IMAGES` entries that exist, and print a skip notice for the rest.
- Run the empty-list check *after* filtering.
- Update the README to show the new option.

### 3. Every row claims the scale bar was "visually confirmed" (from reading) — FIXED

> **Fixed 2026-11-11.** `compute_row` now takes `scale_bar_check` and defaults to `"not checked"`, so the
> GUI always writes that. The batch scripts write `"no blue bar (visually confirmed)"` only when run
> with `--scale-bars-checked`. Documented in `crack_stats_schema.md` and `scripts/batch_stats/README.md`.

**What's wrong.** Both exporters write `"scale_bar_check": "no blue bar (visually confirmed)"`
into every row (`export_crack_stats.py:309`, `export_crack_stats_v3.py:202`). That was true for
the curated thesis batch, where every image was checked by eye. But the GUI calls the same
`compute_row` on any uploaded image, so a spreadsheet downloaded from the GUI asserts a manual
check that never happened.

**Why it matters.** It's a provenance claim in an output file that the method can't support, the
kind of thing `CLAUDE.md`'s evidence-level discipline rules out.

**Fix.** Pass the value in from the caller. The curated batch scripts pass
`"no blue bar (visually confirmed)"`, and the GUI passes `"not checked"`.

---

## Medium

### 4. v3 definitions sheet describes the v1 method (from reading) — FIXED

> **Fixed 2026-11-11** (findings 4–8). Definitions-sheet wording and the console label corrected;
> kink leftovers removed and case counts updated to 12 cases / 4 methods; the example gallery was
> regenerated (12/12 pass, images inlined); calibration docs now use plain names and correct line
> numbers (totals now 3 🟡 / 15 🔴); 59 old paths updated. The only remaining old paths are quoted on
> purpose in this review and the July review.

`add_definitions_sheet.py:88` says the flaking area is "excluded before skeletonization even
runs". That describes v1's two-pass method. v3, the method this sheet is written for,
skeletonizes **once on the uncorrected mask** and drops flake-touching edges afterwards. Reword
it to match v3, for example: "identified after a single skeletonization pass; edges touching it
are omitted".

### 5. Docs still describe the deleted kink feature (verified) — FIXED

The kink module was removed in `58682f6`, but:
- `README.md:133`, `examples/README.md:12,25`, `METHODOLOGY.md:104` and
  `scripts/validation/README.md:9` still say the gallery has "14 cases across all 5 measurement
  methods". It now has **12 cases across 4 methods**.
- `examples/validation_gallery.html`, the shipped example, still contains the two kink cases
  (`kink_60deg`, `straight_line_no_kink`). It was generated before the removal.
- `CALIBRATION.md:35–36` still lists `KINK_WINDOW_PX_PLACEHOLDER` and `KINK_TURN_DEG_PLACEHOLDER`,
  pointing at the deleted `kinks.py`.
- `validation_report.py:16` still has a "Kink detection" section title, and
  `overview_figure.py:2,11` still mentions kinks.

**Fix:** regenerate the example gallery, update the four "14/5" mentions, and delete the two
`CALIBRATION.md` rows and the leftover mentions.

### 6. Calibration docs: wrong line numbers and stray backslashes (verified) — FIXED

- **20 of 34** `file:line` pointers in `CALIBRATION.md` and `docs/calibration_notes.md` are
  wrong. All the `junctions.py` and `corners.py` settings are off by 4–27 lines, because the
  settings moved when their comments were relocated. `skeleton.py`'s four are correct; I fixed
  those last session.
- The settings table writes names as `` `SPUR\\\_PX\\\_PLACEHOLDER` ``. Inside backticks,
  backslashes aren't escapes, so the preview shows them literally (`SPUR\\\_PX...`). This
  happens 23 times.

**Fix.** Use plain names inside backticks. Consider linking to the file without line numbers,
since those go stale every time a comment changes. A small script (the one used for this
review) can re-check them.

### 7. 63 references to file paths that no longer exist (verified) — FIXED

The folder reorganisation moved scripts into `scripts/batch_stats/`, `scripts/validation/` and so
on, but comments and docs still use the old paths. There are 15 distinct dead paths, 63 mentions
in total. The most common are:

| Old path | Mentions | Now at |
|---|---|---|
| `scripts/window_sweep.py` | 11 | `scripts/validation/window_sweep.py` |
| `scripts/corner_window_sweep.py` | 9 | `scripts/validation/` |
| `docs/crack_stats_schema.md` | 9 | `docs/batch_stats/crack_stats_schema.md` |
| `scripts/overview_figure.py` | 7 | `scripts/spatial_overview/` |
| `scripts/export_crack_stats.py` | 6 | `scripts/batch_stats/` |
| `scripts/export_crack_stats_v3.py` | 5 | `scripts/batch_stats/` |

**Fix:** a find-and-replace pass. It's mechanical and safe, and it's what broke the v3 imports
in October.

### 8. Console report names a dropped flaking criterion (from reading) — FIXED

`analyze_image.py:384` prints `[interpreted -- width+solidity flagged ...]` for flaking
candidates. Solidity was dropped as a criterion; `flaking.py` uses width only. Anyone reading a
saved report would be told the wrong method. Change it to "width flagged".

### 9. Two steps get very slow on a full image (from reading) — FIXED

> **Fixed 2026-11-11.** Segment areas come from one `np.bincount` pass. The corner search skips
> outlines whose bounding box lies outside the search radius. On a full T5 image, `analyze_image
> --full-image` went from 194 s to 61 s, with an identical report and edge table (all 1,853 edges).

These are fine on the default corner crop. They scale badly with `--full-image`:
- `edge_metrics.py:272–274` counts each edge's area by scanning the *whole* label image once per
  edge: about 3,400 edges × 55 million pixels on a full T5 image. `np.bincount(labels.ravel())`
  gives every edge's count in one pass, with identical numbers.
- `corners.py:282` checks *every* background contour for *every* junction. Pre-filtering contours
  by bounding box, or one spatial index, would cut this sharply.

### 10. GUI mixes two image regions without saying so (from reading) — LABELLED

> **Labelled 2026-11-11.** Each GUI result now states its region, with a note when corner and
> whole-image results appear together. The console report, xlsx `region_description` and the
> sensitivity sweep's CSVs carry the region's area share (1.5%). The regions themselves still
> differ; making them match would mean validating full-image junction runs.

In `app.py`, the per-image pipeline defaults to the **top-left corner crop**, but crack stats
always run on the **full image**. The "Analyze full image" checkbox only changes the pipeline
part. Results for different regions then appear side by side. Fix it either by labelling each
result with its region, or by making the checkbox apply to both.

### 11. `--n-rows`/`--n-cols` accepted but crash (from reading) — FIXED

> **Fixed 2026-11-11.** Anything but 2×2 is now rejected before the analysis starts. The usage line
> and docs no longer advertise the options.

`overview_figure.py` accepts any grid size, runs the whole analysis, and then crashes at the
final drawing step, because `render_overview_figure` only supports 2×2
(`summary_plots.py:215`). The usage line also still shows `--n-rows 4 --n-cols 4`. Either remove
the two options or reject non-2×2 values up front.

### 12. Open items from the July review

From `docs/reviews/2026-07-05-stage4-corner-junction-kink-rigor-review.md`:
- **#1 still open.** `junctions.py:93–95` still labels the arm direction, bearing and curvature
  `[measured]`. They're extrapolated from a curve fit, so `[interpreted]` fits better.
- **#2 partly addressed.** `precedence.py` now matches arms by identity and reports conflicting
  abutters. The corner method's own "agrees" flag still compares only the T/Y label and sorted
  gaps.
- **#3 still open; #4 partly addressed.** `QUAD_MIN_SPAN_PX` is still 🔴 unswept. The T/Y
  tolerances now have a measured sensitivity check (2026-11-11,
  `docs/junction_tolerance_sensitivity.md`): absolute counts depend strongly on them, and the
  ranking of conditions holds for ±5° / ±25% changes. They're still 🔴 assumed, not calibrated.

---

## Low

### 13. Junction angle fit mixes up both ends of a loop (verified, but rare) — FIXED

> **Fixed 2026-11-11.** Each arm is cut at its first pixel outside the outer radius, and a loop back
> to the same junction at its midpoint, before the ring is picked. New test: the synthetic
> lollipop now reads as T (it read "ambiguous" before). Re-running the T/Y sensitivity sweep on all
> 41 images and 17 cut-off settings gave identical counts, so no reported number changes.

`junctions.py:163–164` picks the points to fit by straight-line distance from the junction. For
a crack that loops back to its own junction, points near the *far* end of the loop also land in
the 5–60 px ring. The fit then mixes both ends and returns a nonsense direction. A synthetic
"lollipop" (a tail plus a ring) read as "ambiguous" instead of T. **On two real images, 0 of
about 7,600 junction arms were affected**, so the real-world impact is negligible. The fix is to
stop at the first point that leaves the outer radius.

### 14. One validation row always says PASS (from reading) — FIXED

> **Fixed 2026-11-11.** The row now checks the bearing against the test suite's 10° axial
> tolerance (`tests/test_anisotropy.py::CIRCULAR_BEARING_TOL_DEG`). Gallery regenerated: 12/12 pass.

`validation_cases.py:323` reports "dominant bearing: expected 0.0" with the verdict hard-coded to
`True`, so the gallery shows PASS whatever is measured. Either check it against a tolerance, or
mark the row "informational".

### 15. Small correctness and consistency nits (from reading) — FIXED

> **Fixed 2026-11-11**, item by item: (a) `ok` in `curvature.py` is defined as "the edge could be
> measured at all"; `failure_reason` names a missing part such as tortuosity. (b) `cache_io.py`
> states the regeneration caveat. (c) `analyze_image.py` now leaves edges next to the flaking cut
> out of its length/width totals, like the export; they keep their row, marked
> `near_flaking_cut`. (d) The console uses the spreadsheet's 0.15 cut-off. 0.5 is a different
> boundary ("grid-like") and stays. (e) `overlay.py` looks paths up by their index.

- `curvature.py:195`: an edge can be `ok=True` with `failure_reason="near_zero_chord_length"`.
  Pick one meaning for `ok`.
- `cache_io.py:7`: says the width map can be regenerated from `mask_corrected`. For v1 runs with
  flaking, the real width map came from a *re-cleaned* copy of that mask, so a regenerated one
  can differ slightly.
- `analyze_image.py` doesn't drop edges next to a flaking cut from its edge-metrics stats, while
  the batch exporter does. The two outputs can disagree on flaked images.
- Three different "anisotropy too low to matter" cut-offs: 0.15 and 0.5 in `xlsx_report.py`, and
  0.2 in `analyze_image.py`.
- `overlay.py` assumes branch numbers run 0, 1, 2, … in order (`path_coordinates(i)`). That's true
  today, but fragile.

### 16. Entry points with no tests — FIXED

> **Fixed 2026-11-11.** `tests/test_entry_points.py` runs `analyze_image.py`, both `compute_row`s,
> the overview figure, `region.py` and the GUI (via Streamlit's `AppTest`) on a small synthetic grid
> with a flake.

The tests cover the library modules well (157 tests). Nothing exercises `analyze_image.py`
(726 lines), `app.py`, `region.py`, or the v3 `compute_row`. That gap is why October's broken v3
import went unnoticed. A single "it runs on a small synthetic image" test for each entry point
would catch that class of break.

---

## Second pass (2026-11-11): new findings

Found while fixing 9–16, by reading the crack-stats path, `precedence.py` and the overview script
again.

### 17. Connectivity graph drops one of two segments joining the same junctions (verified) — FIXED

**What was wrong.** Both batch exporters built the crack network as a plain `networkx.Graph`. When
two different segments join the same pair of junctions (the two sides of a small cell), a
`Graph` keeps only one of them. The giant component's length then came out short, while the
total length, summed from the segment table, counted both. `giant_component_fraction` was
biased low.

**Evidence.** On 4 real images, 0–44 such pairs per image. 75RH_PTFE_v1 went from 0.9907 to 0.9973.
Across the 41-image batch: 27 images have such pairs, and 17 change at the 4th decimal or above
(largest +0.0066).

**Fix.** `crack_network_graph()` builds a `MultiGraph`, which keeps every segment. Used by v1 and v3.
New unit test. `n_components` can't change, since a parallel segment never connects anything
new. Which component counts as the giant one could in principle change, since it's picked by
total length.

### 18. Overview figure skips flaking exclusion (from reading) — FIXED

`overview_figure.py` ran binarize → skeletonize → graph with no flaking step, unlike every other
entry point. On a flaked image, the flake's own interior skeleton mesh went into the rose diagram
and tortuosity histogram as if it were crack. Now it runs the same two-pass flaking exclusion
as `analyze_image.py`.

### 19. A crack ordered before itself is dated instead of reported (from reading) — FIXED

A segment that loops back to its own junction can be both host and abutter of one T, giving
the arrow "X came after X". `networkx` puts a self-arrow in its own one-member group, and the
cycle report only listed groups of 2 or more, so X got a generation number. A self-arrow is now
reported as a cycle, with generation `None`. New unit test.

---

## Readability

| # | Issue | Where | Suggestion |
|---|---|---|---|
| R1 | `main()` is ~550 lines: argument handling, every computation and ~350 lines of printing in one function. | `analyze_image.py:170` | Split into `run_pipeline(args) -> results` and `print_report(results)`. The GUI could then import it instead of running a subprocess. |
| R2 | Settings whose explanation sits **below** the line, the issue you flagged in `skeleton.py`. | `edge_metrics.py:54–69`, `curvature.py:69–98`, `anisotropy.py:75–79`, `overlay.py:69–88`, `xlsx_report.py:44–47` | Same treatment as `skeleton.py`: a short comment above each setting, full text in `docs/calibration_notes.md`. |
| R3 | Opening docstrings of 40–70 lines. | `junctions.py` (67), `anisotropy.py` (65), `curvature.py` (59), `corners.py` (49), `precedence.py` (49), `edge_metrics.py` (42), `overlay.py` (42) | Same treatment as `skeleton.py`/`flaking.py`: ~15-line summary, the rest moved to `docs/design_notes.md`. |
| R4 | Duplicate helpers. | `_bearing_deg` ×3 (`junctions`, `corners`, `anisotropy`); `_angle_diff` ×2 (`corners`, `precedence`); pixel round/clip ×6 (`edge_metrics` ×4, `overlay`, `junctions`); v1 and v3 `compute_row` share ~100 near-identical lines (stats dict, µm conversion) | One shared angle helper module; reuse `graph.path_pixel_indices`; one shared "assemble stats row" function for v1/v3. |
| R5 | ~~Dead code.~~ **Done**: `suppress_non_max` deleted; the kink title went with finding 5. | `_chord_scan.suppress_non_max` (never called); "kink" section title in `validation_report.py` | Delete. |
| R6 | Shipped code refers to Claude's private notes and tools. | `export_crack_stats_v3_batch_bcd.py:9` ("see memory crack-stats-batch-exclusions.md"); `render_area_method_viewer.py:5` ("Claude Artifact") | Replace with the actual reason, or a project doc a reader can open. |

---

## What's in good shape

- **Evidence labels are everywhere** (`[measured]`, `[interpreted]`), and the code largely lives
  up to them.
- **Limitations are shown, not hidden**: the orthogonal-grid anisotropy blind spot, the
  severe-curvature corner case, and the "insufficient data" junction label rather than a guess.
- **The precedence step refuses to guess.** Conflicting abutters emit no arc, and cycles are
  reported, not deleted.
- **Deterministic**: no random numbers in the measurement path; randomness only appears in the
  synthetic test patterns, with fixed seeds.
- **The core crack-stats path** (binarize → skeleton → flaking → graph → stats) is short,
  readable and well tested. It got the most attention in October.

---

## Map of the code

| File | Lines | What it does | Verdict |
|---|---|---|---|
| `src/crackgraph/io_utils.py` | 17 | Load image as grey + colour | Fine |
| `src/crackgraph/binarize.py` | 40 | Otsu threshold → crack mask | Fine |
| `src/crackgraph/skeleton.py` | ~235 | Thin to 1 px, prune junk branches | Fine (tidied) |
| `src/crackgraph/flaking.py` | ~300 | Find and exclude flaked patches | Fine (tidied) |
| `src/crackgraph/graph.py` | 62 | Skeleton → junction/segment network | Fine |
| `src/crackgraph/edge_metrics.py` | 579 | Per-segment length, width, 4 area estimates | #9 speed, R2 |
| `src/crackgraph/junctions.py` | 476 | Classify junctions T / Y / ambiguous | #12, #13, R3 |
| `src/crackgraph/corners.py` | 315 | Independent corner-based cross-check | **#1 bug**, #9, R3 |
| `src/crackgraph/precedence.py` | 238 | "Which crack came first" graph | Sound logic; R3 |
| `src/crackgraph/curvature.py` | 247 | Bending and tortuosity per segment | #15, R2, R3 |
| `src/crackgraph/anisotropy.py` | 266 | Preferred crack direction | Sound; R2, R3 |
| `src/crackgraph/_chord_scan.py` | 55 | Shared angle-scan helper | R5 dead function |
| `src/crackgraph/overlay.py` | 573 | Draw results on the micrograph | #15, R2 |
| `src/crackgraph/xlsx_report.py` | 345 | Per-run Excel rows | #15, R2 |
| `src/crackgraph/cache_io.py` | 161 | Save/load intermediate results | #15 |
| `src/crackgraph/summary_plots.py` | 244 | Rose and histogram plots | #11, stale comments |
| `src/crackgraph/html_report.py` | 218 | Master HTML report | Fine |
| `src/crackgraph/region.py`, `tiling.py` | 44, 54 | Crop and grid helpers | Fine; untested (`region`) |
| `src/crackgraph/validation_cases.py`, `validation_report.py` | 402, 110 | Synthetic gallery | #5, #14 |
| `src/crackgraph/synthetic*.py` | 1411, 99 | Draw synthetic test patterns | Skimmed; stale paths |
| `src/crackgraph/pipeline_figures.py` | 116 | Figure panels | Stale paths |
| `src/analyze_image.py` | 726 | Per-image CLI | #8, #15, #16, R1 |
| `scripts/batch_stats/*` | ~900 | Spreadsheet exports | **#2, #3**, #4, R4, R6 |
| `scripts/spatial_overview/*` | 165 | Quadrant figure + report | #11 |
| `scripts/validation/*` | ~2,200 | Sweeps and galleries | Stale paths; #2 for `skeleton_loop_sweep` |
| `scripts/experimental/tracing_poc.py` | 450 | Throwaway proof of concept | Skimmed; out of scope |
| `app.py` | 442 | Local GUI | #3, #10, #16 |
| `tests/` | ~3,100 | 157 tests, all passing | #16 gaps |

---

## Suggested order of work

1. **#1 corner angle averaging.** Small fix, real effect on a reported validation signal. Add the
   regression test.
2. **#2 and #3 exporter path and scale-bar claim.** Small, and they make deliverable #2 runnable
   and honest.
3. **#4–#8 doc accuracy.** Mostly find-and-replace. Regenerate the example gallery.
4. **R2/R3 docstring and comment tidy-up**, same pattern as `skeleton.py`.
5. **#9–#16 and R1/R4** as time allows. R1 (splitting `analyze_image.main`) is the largest change
   here, so agree on it before starting.
