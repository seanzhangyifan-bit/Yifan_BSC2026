# CLAUDE.md

Operating guide for Claude Code working in this repository. Read this before proposing changes.

## What this project is

A BSc thesis (KIT, Thin Film Technology group) on PEMFC catalyst layer ink formulation and coating, centred on comparing short-side-chain (SSC) vs long-side-chain (LSC) PFSA ionomers and their effect on catalyst layer structure, cracking, and performance. Scope: light-duty-vehicle CCMs, low Pt loading (0.2–0.4 mg/cm²), direct coating on PTFE at four Rakelspalt (doctor-blade gap) settings.

The code in this repo is one component of that thesis: **a tool to analyse crack patterns in catalyst-layer micrographs and characterise how sequential vs concurrent the cracking was.** It is not a general crack-detection package and should not grow into one.

## The one thing to understand before writing code here

The analysis reconstructs a **partial order** on crack growth, not a global chronology. This distinction is load-bearing and must not be eroded "for convenience":

- Input is a single micrograph (no time-lapse video). Therefore there are **no external timestamps / boundary conditions** available.
- A T-junction (one crack meeting another at ~90°) certifies exactly one *local* fact: the crack that abuts arrived after the crack it hit, **at that point**. Nothing more.
- The correct output is a partial order (a poset / DAG) that claims only what the geometry supports. Its **incompleteness is a measured result, not a failure.**
- Do **not** add code that fabricates a total ordering, guesses missing relations, or otherwise presents more temporal information than the junction geometry licenses. If a function would need a timestamp we don't have, it should surface the gap, not fill it.

The headline quantities the tool should produce are: junction-type census (T vs Y vs higher-valence), and the **width `w`** of the precedence poset (size of the largest set of mutually-undatable cracks, via a maximum-antichain / bipartite-matching computation). `w` is simultaneously (a) the count of unresolved orderings, (b) an index of how concurrent vs hierarchical the cracking was, and (c) a falsifiable check on the quasi-static sequential-cracking hypothesis. Small `w` corroborates it; large `w` is a genuine and reportable tension.

## Atoms: arcs, not whole cracks

Model the network as a planar graph: nodes = junctions/endpoints, edges = crack segments.

- Prefer **growth-arcs** (oriented edges) as the atoms of the partial order, because cracks grow concurrently and a through-line may actually be two arrested cracks meeting head-on (en-passant / pseudo-junctions).
- Collapsing collinear through-segments into a single "crack" is a **hypothesis that must be evidence-backed** (straight continuous path + matching width + no arrest feature at the vertex), never a default. Treat each collapse as a testable merge that reduces `w`, and make it possible to report `w` both with and without collapse.
- Reporting how much `w` drops as collapse-licensing evidence is added is a legitimate way to show how much chronology is *earned by geometry* vs *assumed*.

## Pipeline shape (keep these stages separate and independently testable)

1. Binarise micrograph (adaptive threshold). Only reach for ML segmentation if simple thresholding genuinely fails — SEM micrographs are usually high-contrast enough.
   - **Flaking/delamination exclusion, between stages 1 and 2** (`src/crackgraph/flaking.py`): some samples (seen so far on membrane-substrate T2/T3/T4) have patches where the catalyst layer has physically flaked off, exposing substrate — bright under Otsu like a crack, but it's missing material, not a fracture, and we have zero evidence what crack pattern (if any) existed under it. A scout skeletonize pass gets a width signal; pixels far wider than the image's own typical crack width are grown back out to their true boundary and excluded from the mask *before* the real skeletonize runs — treated as background, not specially handled downstream. Width is the single identification criterion, deliberately — a solidity-based second criterion was tried and dropped after it excluded a confirmed real (elongated) delamination case; see the module docstring. Edges whose path comes within one reference-crack-width of the exclusion boundary at any point (not just their endpoints) are flagged and dropped from length/width stats (kept in the connectivity graph — the topology is real, only the reported length isn't). See the module docstring for why a "smooth the boundary to look natural" approach was considered and rejected (shapes the output, doesn't measure anything) in favor of this stats-level exclusion.
2. Skeletonise (homotopy-preserving thinning). Prune spurs/hairs shorter than ~film-thickness equivalent.
3. Extract attributed planar graph: nodes, edges, and **the full pixel polyline per edge** (needed for angle/curvature/width).
4. Measure per junction on an **annulus** around the vertex: inner radius a few px (skeleton jitter near vertices is severe), outer radius ~h/2 (local approach direction, not far-field). Classify T vs Y; for each T emit `abutter ≺ host` (read the open side of `≺` as pointing to the *older* crack: host is older, abutter is younger).
5. Build precedence graph → transitive closure → **DAG/cycle check** → poset. Cycles = misread junctions or genuinely near-simultaneous cracking; report minimum-feedback-arc-set size as a data-quality / simultaneity metric rather than silently deleting.
6. Compute width `w` (Dilworth / König; use the library rather than hand-rolling). Report `w`, `w-1`, junction census, generation counts.

Stages 1–4 are largely off-the-shelf; stage 5–6 is the actual contribution. Don't gold-plate 1–4.

## Three semi-independent chronometers

Junction **angle**, approach **curvature** (younger crack curls toward its T; measure at the annulus, not by average edge direction), and crack **width** (from the pre-skeleton mask via distance transform; earlier cracks tend wider due to post-crack drying shrinkage). Their **mutual agreement rate is a validation signal that needs no ground truth.** Systematic disagreement is physics (pinning, interfacial slip, late widening), so log disagreements, don't smooth them over.

## Libraries

- `scikit-image` for threshold/skeleton/distance-transform.
- `Skan` (skeleton-analysis.org) for skeleton→branch-graph — does most of stage 2–3; distinguishes junctions/endpoints, flags cycles.
- `sknw` when per-edge pixel polylines in a NetworkX graph are wanted.
- `networkx` for the poset work (transitive closure, matching-based max-antichain, feedback arc set).
- Package management in this environment: `pip install <x> --break-system-packages`.

## Data layout

- Raw micrographs live in `data/raw/` (gitignored from this repo; it is its own separate git repository), organized in subfolders by experiment/condition -- currently `T5/` and `humidity_loading/`, each holding one `.jpg` per micrograph (e.g. `data/raw/T5/T5-M_H190_v1_ro000001.jpg`). `data/processed/` exists alongside it but is currently empty.
- Analysis is currently run on a fixed top-left corner crop only, not the full image (see `src/crackgraph/region.py`'s `default_corner_crop` and `src/analyze_image.py`'s `--full-image` flag, which is deferred -- see README): crop size is 1/8 of image width (`corner_frac=0.125`), inset from the true top-left corner by a margin of 2% of image width (`edge_margin_frac=0.02`) on both axes. These are the pipeline's working CLI defaults; pass `--corner-frac`/`--edge-margin-frac` to override for a one-off run rather than changing the default.
- `analyze_image.py` (and `scripts/overview_figure.py`, below) nest their output under `outputs/<coating>/`, where `<coating>` is the image's source subfolder name (`T5`, `humidity_loading`) -- so outputs from different coatings/sample batches don't pile up flat in one directory.

## Multi-section overview figure & HTML report

A second, independent entry point for a first look at spatial variation across a whole coating -- not part of `analyze_image.py`'s per-region flow.

- **`scripts/overview_figure.py <image_path> [--n-rows 2] [--n-cols 2] [--out-dir outputs]`**: times one pass of the curvature/anisotropy pipeline slice (binarize -> skeletonize -> graph -> curvature -> anisotropy -- deliberately *not* junctions/kinks/corner-cross-check, which this doesn't need) over the whole image, then again over a coarse `n_rows x n_cols` grid of non-overlapping sections (`src/crackgraph/tiling.py`'s `grid_tiles`), and compiles everything into one figure (`src/crackgraph/summary_plots.py`'s `render_overview_figure`).
- **Figure layout (specific to the 2x2/quarters default, not a generic N x M layout)**: a big display of the whole raw micrograph in the center; each quadrant's rose + tortuosity-hist cluster in the figure corner matching that quadrant's actual position in the source image (top-left quadrant's cluster in the figure's top-left corner, etc.); the whole image's *own* rose/tortuosity cluster (its analysis result, distinct from the raw-image display above it) in a row below everything. An earlier flat-list-of-rows layout (one row per section) was tried first and replaced -- 16 sections (the original 4x4 default) made for a tall, scroll-heavy figure; quarters plus this spatial layout reads much faster. Curvature is currently omitted from this figure (kept only in the standalone `render_curvature_histogram`/xlsx export) -- dropped for readability, may come back later; `_plot_curvature_hist_on_axes` was split so `_plot_tortuosity_hist_on_ax` could be reused alone here.
- **Decisions already made, so a future session doesn't silently redo them differently**: the grid is a coarse, independent tiling decoupled from `region.py`'s `corner_frac` -- tiling at corner-crop size would give ~50-100+ tiles, far too many for this figure. Default is 2x2 (quarters); `render_overview_figure` asserts exactly 4 sections and assumes grid_tiles' row-major order (r0c0, r0c1, r1c0, r1c1). `grid_tiles` does **not** apply `edge_margin_frac` -- every pixel is covered, edge to edge. Per-quadrant image thumbnails were considered and dropped -- only the whole image is shown, big, once.
- **`src/crackgraph/html_report.py`**: one master HTML report (`outputs/report.html`) covering *every* coating and image analyzed so far -- explicitly not one HTML per coating and not one per image. A small JSON registry (`outputs/report_data.json`) is the source of truth; the HTML is always regenerated in full from it (`update_master_report`), grouped by coating, one image block per image. Re-running on the same `(coating, image_stem)` replaces its existing block instead of duplicating it.
- **What's built vs. deferred**: today, each image's block in the master HTML holds only its overview figure. Embedding overlays, per-image xlsx-style numeric tables, or other per-image outputs into the same HTML is future work, not started.

## Standalone crack-stats export (for the sibling `image_visualization` repo)

A fourth, independent entry point -- a stripped-down stage 1-3 only (binarize -> skeletonize ->
graph extraction, no junctions/anisotropy/curvature/ordering) batch export, built for external
consumption rather than in-repo analysis.

- **`scripts/export_crack_stats.py`**: globs `data/raw/**/*_mm000001.jpg` plus an explicit
  `ADDITIONAL_IMAGES` override list (for samples where the default `000001` index is wrong -- e.g.
  an undersized non-standard capture), excludes `CONFIRMED_SCALE_BAR_IMAGES` (files matching the
  `_mm000001` naming pattern but directly verified to carry a scale bar anyway), and writes
  `outputs/crack_stats.xlsx`. Full column reference, evidence-level legend (measured/interpreted/
  calibrated), and calibration-factor provenance/scope live in `docs/crack_stats_schema.md` -- read
  that file rather than re-deriving any of it here.
- **Downstream consumer, stated explicitly**: `../image_visualization` ("figlib" in its own docs) is
  a sibling Claude Code project, a figure-making toolkit over the same `all_pics/` source catalogue
  this repo's `data/raw/` is drawn from. It reads `crack_stats.xlsx` via `figlib/crack_data.py` and
  never hand-edits it -- corrections happen here and get re-copied over there. This is the actual
  "different Claude program" the export exists for; keep `docs/crack_stats_schema.md` honest about
  anything figlib's own code (`_sample_id()`, its `crack_levels_table` configs) already assumes,
  rather than duplicating figlib's own docs here.
- **`v1`/`v2` replicate convention**: a filename's `v#` is a physically distinct replicate capture of
  the same condition, not a document-revision number. The export includes every replicate that
  passes the scale-bar/size checks -- it does not collapse multiple replicates down to one canonical
  row per condition. Consumers wanting per-condition statistics group rows by `image_filename` with
  the trailing `_mm######.jpg` index stripped, and average only where >=2 replicates exist (matching
  what figlib's own `crack_levels_table` figures already do).
- **Naming-convention caveat**: the `mm000000`/`mm000001` naming pattern does *not* reliably predict
  which file carries the burned-in blue scale bar -- every candidate needs a direct visual check
  (bottom-right corner crop) before inclusion. Two confirmed exceptions exist so far (details in
  `docs/crack_stats_schema.md` §2/§2b) -- don't re-trust the naming pattern alone if this export is
  ever regenerated against a larger image set.

## Synthetic-pattern validation gallery

A third independent entry point: a visual, human-reviewable companion to the numeric-tolerance pytest suite (`tests/test_junction_angle.py`, `test_corners.py`, `test_curvature.py`, `test_kinks.py`, `test_anisotropy.py`), not a replacement for it.

- **`scripts/validation_gallery.py [--out-dir outputs/validation]`**: runs a fixed battery of 14 synthetic cases (`src/crackgraph/validation_cases.py`, covering all 5 measurement methods) through the real pipeline, and compiles each case's overlay/rose image plus an expected-vs-measured table into one page (`src/crackgraph/validation_report.py`'s `render_validation_report`, in `outputs/validation/report.html`).
- Every tolerance used for a case's PASS/FAIL verdict is duplicated (with a cross-reference comment), not imported, from the corresponding `tests/test_*.py` constant — tests aren't a dependency of `src/`. Keep them in sync by hand if a test's tolerance changes.
- Two cases exist specifically to show a known method limitation honestly rather than hide it: `curved_t_junction_r30_corner_limitation` (corner cross-check doesn't resolve cleanly on a severely curved host at the default window, even though the tangent fit still does) and `anisotropy_orthogonal_blind_spot` (the 2nd-order orientation tensor reads an orthogonal grid as isotropic; only the rose histogram reveals the two peaks). Neither has a fabricated pass condition — see their row logic if extending this pattern.
- Ground truth is not bundled into `synthetic.py`'s return value (still image-only, matching every existing test file's convention) — each case function re-derives its own expected values from the same arguments it passes to the generator.

## Documentation map

This file is the technical/scientific operating guide. Other docs cover other audiences —
don't duplicate their content here, just know they exist:

- `README.md` — how to run the pipeline, CLI flags, output layout, and a "Libraries and
  code architecture" overview for a reader who doesn't need the thesis framing.
- `GLOSSARY.md` — one-line definitions of the terms used above (poset, antichain, width
  `w`, T/Y-junction, abutter/host, annulus, generation, growth-arc).
- `CALIBRATION.md` — status table (🟢 derived / 🟡 empirical uncalibrated / 🔴 assumed) for
  every tunable constant, with file:line pointers.
- `docs/calibration_notes.md` — the full rationale for each constant, relocated verbatim
  from what used to be multi-line inline comments.
- `docs/crack_stats_schema.md` — column-by-column reference for `outputs/crack_stats.xlsx`
  (the standalone batch export, see "Standalone crack-stats export" above).
- `docs/crack_stats_v2_status.md` / `docs/crack_stats_v3_status.md` — running status docs for
  two follow-on batch-export efforts: v2 re-runs the original (v1) two-pass methodology over a
  scoped 19-image batch with flaking exclusion and thesis-notation columns; v3 is an independent,
  alternate single-pass methodology (skip the second skeletonize, omit flake-touching edges by
  direct mask membership instead of a distance buffer), cross-validated against v1/v2 rather than
  replacing it — both remain runnable side by side.
- `docs/dynamic_tracking_hypothetical.md` — a design discussion (not implemented, not tested) on
  whether/how this pipeline could extend to in-situ drying video instead of static micrographs;
  `scripts/tracing_poc.py` is a throwaway, unintegrated proof-of-concept tied to one idea in it.
  Both are explicitly exploratory future-direction material, not part of the validated pipeline.
- `docs/reviews/` — point-in-time methodology/rigor review findings.
- `.vscode/launch.json` — VS Code Run/Debug configs (prompts for an image path).

## Conventions & guardrails

- Every claim-bearing output should be traceable to what the method can actually support. This project uses an evidence-level discipline elsewhere in the thesis (`[measured]` / `[interpreted]` / `[speculated]` / `[cited]`); mirror that spirit in comments and docstrings — label what a number is, not just what it is called. E.g. "T-fraction is `[measured]`; the inference that small `w` implies quasi-static cracking is `[interpreted]`."
- Prefer deterministic, reproducible measurement over anything that "looks about right". This is going in a thesis; hand-tuned magic constants need a stated justification (ideally tied to `h`).
- Keep functions honest about uncertainty: near-120° junctions carry weak/no ordering signal — emit no constraint there rather than a low-confidence guess.
- Don't introduce dependencies on cloud services, browser storage, or anything non-reproducible offline.
- Ask before large refactors. Output files for the human to merge manually; don't assume write-back to source data.

## Reference spine (for context, not to be re-derived in code)

Thin-film fracture mechanics behind the analysis: Beuth 1992 (plane-strain channelling, defines `g(α,β)`), Xia & Hutchinson 2000 (shear-lag model, exponential stress recovery, KII=0 path selection, curvature/spiral results), Goehring 2012 (rectilinear→hexagonal evolution, annulus angle method, T-junctions as timing record). Hierarchical-division / ordering precedent: Bohn, Pauchard & Couder 2005. The math of the reconstruction is planar graph theory + order theory (posets, Dilworth's theorem); the front-half image work is homotopy-preserving skeletonisation.

Anisotropy/curvature sidequest (see `crackgraph/anisotropy.py` and `crackgraph/curvature.py` docstrings for the full attribution): axial circular statistics and the doubled-angle construction — Mardia & Jupp, *Directional Statistics*, Wiley, 2000; Fisher, *Statistical Analysis of Circular Data*, Cambridge University Press, 1993 (the more common reference in earth-science fracture/joint-orientation work). The 2nd-order orientation tensor formalism (and its known insufficiency, motivating a 4th-order tensor) — Advani & Tucker, "The Use of Tensors to Describe and Predict Fiber Orientation in Short Fiber Composites", *Journal of Rheology*, 1987. Chord-angle/turning-angle discrete curvature estimation on digitized curves — Rosenfeld & Johnston, "Angle Detection on Digital Curves", *IEEE Transactions on Computers* C-22(9), 1973 (an alternative standard estimator, the 3-point circle fit / Menger curvature, was not used — chosen instead for compatibility with the existing `kinks.py` scan, not for a documented accuracy advantage). Tortuosity (arc/chord) is a generic, uncredited-to-one-source geometric ratio, used with the same definition in crack-path roughness work (Bouchaud, "Scaling properties of cracks", *J. Phys.: Condens. Matter* 9, 4319, 1997), vascular tortuosity, and river sinuosity.

## Scope discipline

Floor deliverable (do this first, it is guaranteed reportable): graph extraction + junction census + generation counts across the four Rakelspalt settings and SSC vs LSC. Ceiling deliverable: full arc-level poset with width computation and cross-condition comparison. Build the floor before climbing; if T-junctions turn out rare in these patterns, the ordering apparatus has little to work on and that is itself a cheap, useful finding.
