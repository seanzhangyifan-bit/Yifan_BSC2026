# Methodology

The scientific and architectural reasoning behind this pipeline — read this before the other
docs make full sense.

## What this project is

A BSc thesis (KIT, Thin Film Technology group) on PEMFC catalyst layer ink formulation and coating, centred on comparing short-side-chain (SSC) vs long-side-chain (LSC) PFSA ionomers and their effect on catalyst layer structure, cracking, and performance. Scope: light-duty-vehicle CCMs, low Pt loading (0.2–0.4 mg/cm²), direct coating on PTFE at four Rakelspalt (doctor-blade gap) settings.

The code in this repo is one component of that thesis: **a tool to turn catalyst-layer crack micrographs into numbers that let crack patterns be compared across conditions** (ionomer type, Rakelspalt, substrate, humidity). It is not a general crack-detection package.

## What the results are

The main output is the per-image crack statistics from the batch export (`scripts/batch_stats/`): crack area fraction, flaked area, crack width, segment count and length, and network connectivity (see `docs/batch_stats/crack_stats_schema.md`). The per-image analysis (`src/analyze_image.py`) adds per-segment geometry, curvature/tortuosity and orientation anisotropy for a closer look at one image.

How to judge an error in the pipeline: by its effect on those numbers. Compare the shift with (a) the spread between `v1`/`v2` replicates of the same condition and (b) the gap between the conditions being compared. Errors that grow systematically with crack width or density matter more than random ones, because they can tilt a comparison between conditions.

## Pipeline stages

1. Binarise micrograph (adaptive threshold).
   - **Flaking/delamination exclusion, after stage 2** (`src/crackgraph/flaking.py`): some samples (seen so far on membrane-substrate T2/T3/T4) have patches where the catalyst layer has physically flaked off, exposing substrate — bright under Otsu like a crack, but it's missing material, not a fracture, and there's zero evidence what crack pattern (if any) existed under it. The mask is skeletonized once; pixels far wider than the image's own typical crack width are grown back out to their true boundary, and every skeleton edge with a pixel inside that region is omitted from the stats and from the connectivity graph, so nothing connects through a flaked patch. Width is the single identification criterion, deliberately — a solidity-based second criterion was tried and dropped after it excluded a confirmed real (elongated) delamination case; see the module docstring. See the module docstring for why a "smooth the boundary to look natural" approach was considered and rejected (shapes the output, doesn't measure anything).
2. Skeletonise (homotopy-preserving thinning). Prune spurs/hairs shorter than ~film-thickness equivalent.
3. Extract attributed planar graph: nodes, edges, and **the full pixel polyline per edge** (needed for angle/curvature/width).
4. Measure per segment: length, width (from the pre-skeleton mask via distance transform) and area; per image: curvature/tortuosity and orientation anisotropy.

All stages draw on off-the-shelf image-processing libraries (scikit-image, skan); the code around them chooses settings, removes artefacts and labels what each number is.

## Libraries

- `scikit-image` for threshold/skeleton/distance-transform.
- `Skan` (skeleton-analysis.org) for skeleton→branch-graph — does most of stage 2–3; distinguishes junctions/endpoints, flags cycles.
- `sknw` when per-edge pixel polylines in a NetworkX graph are wanted.
- `networkx` for the connectivity graph in the batch export (connected components, giant component).

## Data layout

- The private raw micrograph collection this pipeline was developed against lives in `data/raw/` (not bundled in this export — see the root README's "What's not included"), organized in subfolders by experiment/condition -- currently `T5/` and `humidity_loading/`, each holding one `.jpg` per micrograph (e.g. `data/raw/T5/T5-M_H190_v1_ro000001.jpg`).
- Analysis is currently run on a fixed top-left corner crop only, not the full image (see `src/crackgraph/region.py`'s `default_corner_crop` and `src/analyze_image.py`'s `--full-image` flag, which is deferred -- see README): crop size is 1/8 of image width (`corner_frac=0.125`), inset from the true top-left corner by a margin of 2% of image width (`edge_margin_frac=0.02`) on both axes. These are the pipeline's working CLI defaults; pass `--corner-frac`/`--edge-margin-frac` to override for a one-off run rather than changing the default. That crop is about 1.5% of the image area, so numbers from it are a corner sample: the console report, the xlsx `region_description` column and the GUI all state the region and its area share, and they must not be read alongside the whole-image batch crack stats as if both described the same area.
- `analyze_image.py` (and `scripts/spatial_overview/overview_figure.py`, below) nest their output under `outputs/<coating>/`, where `<coating>` is the image's source subfolder name (`T5`, `humidity_loading`) -- so outputs from different coatings/sample batches don't pile up flat in one directory.

## Multi-section overview figure & HTML report

A second, independent entry point for a first look at spatial variation across a whole coating -- not part of `analyze_image.py`'s per-region flow.

- **`scripts/spatial_overview/overview_figure.py <image_path> [--out-dir outputs]`**: times one pass of the curvature/anisotropy pipeline slice (binarize -> flaking exclusion -> skeletonize -> graph -> curvature -> anisotropy) over the whole image, then again over a 2x2 grid of non-overlapping quadrants (other grid sizes are rejected, since the layout below is 2x2-only) (`src/crackgraph/tiling.py`'s `grid_tiles`), and compiles everything into one figure (`src/crackgraph/summary_plots.py`'s `render_overview_figure`).
- **Figure layout (specific to the 2x2/quarters default, not a generic N x M layout)**: a big display of the whole raw micrograph in the center; each quadrant's rose + tortuosity-hist cluster in the figure corner matching that quadrant's actual position in the source image (top-left quadrant's cluster in the figure's top-left corner, etc.); the whole image's *own* rose/tortuosity cluster (its analysis result, distinct from the raw-image display above it) in a row below everything. An earlier flat-list-of-rows layout (one row per section) was tried first and replaced -- 16 sections (the original 4x4 default) made for a tall, scroll-heavy figure; quarters plus this spatial layout reads much faster. Curvature is currently omitted from this figure (kept only in the standalone `render_curvature_histogram`/xlsx export) -- dropped for readability; `_plot_curvature_hist_on_axes` was split so `_plot_tortuosity_hist_on_ax` could be reused alone here.
- **Decisions already made**: the grid is a coarse, independent tiling decoupled from `region.py`'s `corner_frac` -- tiling at corner-crop size would give ~50-100+ tiles, far too many for this figure. Default is 2x2 (quarters); `render_overview_figure` asserts exactly 4 sections and assumes grid_tiles' row-major order (r0c0, r0c1, r1c0, r1c1). `grid_tiles` does **not** apply `edge_margin_frac` -- every pixel is covered, edge to edge. Per-quadrant image thumbnails were considered and dropped -- only the whole image is shown, big, once.
- **`src/crackgraph/html_report.py`**: one master HTML report (`outputs/report.html`) covering *every* coating and image analyzed so far -- explicitly not one HTML per coating and not one per image. A small JSON registry (`outputs/report_data.json`) is the source of truth; the HTML is always regenerated in full from it (`update_master_report`), grouped by coating, one image block per image. Re-running on the same `(coating, image_stem)` replaces its existing block instead of duplicating it.
- **What's built vs. deferred**: today, each image's block in the master HTML holds only its overview figure. Embedding overlays, per-image xlsx-style numeric tables, or other per-image outputs into the same HTML is future work, not started.

## Standalone crack-stats export (for the sibling `image_visualization` repo)

A fourth, independent entry point -- a stripped-down stage 1-3 only (binarize -> skeletonize ->
graph extraction, no anisotropy/curvature) batch export, built for external
consumption rather than in-repo analysis.

- **`scripts/batch_stats/export_crack_stats.py`**: gives a row to every image file under `--data-dir`
  (any subfolder) and writes `outputs/crack_stats.xlsx`. It does not select images by file name;
  which images belong in a table is the user's choice (the folder's contents, or the GUI's uploads).
  Full column reference, evidence-level legend (measured/interpreted/
  calibrated), and calibration-factor provenance/scope live in `docs/batch_stats/crack_stats_schema.md`
  -- read that file rather than re-deriving any of it here.
- **Downstream consumer, stated explicitly**: `../image_visualization` ("figlib" in its own docs) is
  a sibling project, a figure-making toolkit over the same `all_pics/` source catalogue this repo's
  `data/raw/` is drawn from. It reads `crack_stats.xlsx` via `figlib/crack_data.py` and never
  hand-edits it -- corrections happen here and get re-copied over there. This is the actual external
  consumer this export exists for; keep `docs/batch_stats/crack_stats_schema.md` honest about anything
  figlib's own code (`_sample_id()`, its `crack_levels_table` configs) already assumes, rather than
  duplicating figlib's own docs here.
- **`v1`/`v2` replicate convention**: a filename's `v#` is a physically distinct replicate capture of
  the same condition, not a document-revision number. Include every replicate that passes the
  scale-bar/size checks when choosing images, rather than one canonical image per condition. Consumers wanting per-condition statistics group rows by `image_filename` with
  the trailing `_mm######.jpg` index stripped, and average only where >=2 replicates exist (matching
  what figlib's own `crack_levels_table` figures already do).
- **Naming-convention caveat, when choosing images**: the `mm000000`/`mm000001` naming pattern does
  *not* reliably predict which file carries the burned-in blue scale bar -- check every candidate by
  eye (bottom-right corner crop) before including it. The export itself doesn't look at names.

## Synthetic-pattern validation gallery

A third independent entry point: a visual, human-reviewable companion to the numeric-tolerance pytest suite (`tests/test_curvature.py`, `test_anisotropy.py`), not a replacement for it.

- **`scripts/validation/validation_gallery.py [--out-dir outputs/validation]`**: runs a fixed battery of 5 synthetic cases (`src/crackgraph/validation_cases.py`, covering 2 measurement methods) through the real pipeline, and compiles each case's overlay/rose image plus an expected-vs-measured table into one page (`src/crackgraph/validation_report.py`'s `render_validation_report`, in `outputs/validation/report.html`).
- Every tolerance used for a case's PASS/FAIL verdict is duplicated (with a cross-reference comment), not imported, from the corresponding `tests/test_*.py` constant — tests aren't a dependency of `src/`.
- One case exists specifically to show a known method limitation honestly rather than hide it: `anisotropy_orthogonal_blind_spot` (the 2nd-order orientation tensor reads an orthogonal grid as isotropic; only the rose histogram reveals the two peaks). It has no fabricated pass condition.
- Ground truth is not bundled into `synthetic.py`'s return value (image-only, matching every existing test file's convention) — each case function re-derives its own expected values from the same arguments it passes to the generator.

## Documentation map

This file is the technical/scientific reference. Other docs cover other audiences —
they're not duplicated here:

- `README.md` — how to run the pipeline, CLI flags, output layout, and a "Libraries and
  code architecture" overview for a reader who doesn't need the thesis framing.
- `GLOSSARY.md` — one-line definitions of the terms used in the code and docs (node, degree,
  segment, giant component, tortuosity, anisotropy).
- `CALIBRATION.md` — status table (🟢 derived / 🟡 empirical uncalibrated / 🔴 assumed) for
  every tunable constant, with file:line pointers.
- `docs/walkthrough/` — a page-by-page code walkthrough, including the rationale for each
  tunable constant and the design of `skeleton.py` and `flaking.py`.
- `docs/batch_stats/crack_stats_schema.md` — column-by-column reference for `outputs/crack_stats.xlsx`
  (the standalone batch export, see "Standalone crack-stats export" above), including the
  thesis-notation column mapping.
- `docs/experimental/dynamic_tracking_hypothetical.md` — a design discussion (not implemented, not
  tested) on whether/how this pipeline could extend to in-situ drying video instead of static
  micrographs; `scripts/experimental/tracing_poc.py` is a throwaway, unintegrated proof-of-concept
  tied to one idea in it. Both are explicitly exploratory future-direction material, not part of the
  validated pipeline.
- `docs/reviews/` — point-in-time methodology/rigor review findings.

## Design principles

- Every claim-bearing output is traceable to what the method can actually support. This project uses an evidence-level discipline elsewhere in the thesis (`[measured]` / `[interpreted]` / `[speculated]` / `[cited]`) that carries into the code and console output — labeling what a number is, not just what it is called. E.g. "crack area fraction is `[measured]`; which segment owns a pixel inside a junction blob is `[interpreted]`."
- Deterministic, reproducible measurement is preferred over anything that "looks about right" — hand-tuned magic constants carry a stated justification (ideally tied to `h`), tracked in `CALIBRATION.md`.
- The tool stays honest about uncertainty: where a number can only be bracketed (e.g. per-segment area near junctions), it reports the bounds rather than one falsely exact value.

## Reference spine (for context, not to be re-derived in code)

Thin-film fracture mechanics behind the analysis: Beuth 1992 (plane-strain channelling, defines `g(α,β)`), Xia & Hutchinson 2000 (shear-lag model, exponential stress recovery, curvature/spiral results), Goehring 2012 (rectilinear→hexagonal crack-network evolution), Bohn, Pauchard & Couder 2005 (hierarchical crack patterns). The image work is homotopy-preserving skeletonisation plus planar graph extraction.

Anisotropy/curvature sidequest (see `crackgraph/anisotropy.py` and `crackgraph/curvature.py` docstrings for the full attribution): axial circular statistics and the doubled-angle construction — Mardia & Jupp, *Directional Statistics*, Wiley, 2000; Fisher, *Statistical Analysis of Circular Data*, Cambridge University Press, 1993 (the more common reference in earth-science fracture/joint-orientation work). The 2nd-order orientation tensor formalism (and its known insufficiency, motivating a 4th-order tensor) — Advani & Tucker, "The Use of Tensors to Describe and Predict Fiber Orientation in Short Fiber Composites", *Journal of Rheology*, 1987. Chord-angle/turning-angle discrete curvature estimation on digitized curves — Rosenfeld & Johnston, "Angle Detection on Digital Curves", *IEEE Transactions on Computers* C-22(9), 1973 (an alternative standard estimator, the 3-point circle fit / Menger curvature, was not used — chosen for consistency with the shared chord-based scan in `_chord_scan.py`, not for a documented accuracy advantage). Tortuosity (arc/chord) is a generic, uncredited-to-one-source geometric ratio, used with the same definition in crack-path roughness work (Bouchaud, "Scaling properties of cracks", *J. Phys.: Condens. Matter* 9, 4319, 1997), vascular tortuosity, and river sinuosity.

## Scope discipline

Main deliverable: reliable, comparable per-image crack statistics across the conditions — Rakelspalt settings, SSC vs LSC, substrate, humidity — with known biases measured and stated. Work that makes these numbers trustworthy and comparable comes first.
