# Methodology

Codebase originally developed as part of a BSc thesis (Zhang 2026, KIT Thin Film Technology group) on PEMFC catalyst layer ink formulation and coating, centered on comparing short-side-chain (SSC) vs long-side-chain (LSC) PFSA ionomers and their effect on catalyst layer structure and cracking.

The code in this repo is one component of that thesis: **a tool to turn catalyst-layer crack micrographs into numbers that let crack patterns be compared across conditions** (ionomer type, Rakelspalt, substrate, humidity).

## What the results are

The main output is the per-image crack statistics on the whole image: crack area fraction, flaked area, crack width, segment count and length, and network connectivity (see `docs/batch_stats/crack_stats_schema.md`). The same tool can also report them per region (the centre, or cells of a grid), and add curvature/tortuosity, orientation anisotropy and a per-segment table.

How to judge an error in the pipeline: by its effect on those numbers. Compare the shift with (a) the spread between `v1`/`v2` replicates of the same condition and (b) the gap between the conditions being compared. Errors that grow systematically with crack width or density matter more than random ones, because they can tilt a comparison between conditions.

## Pipeline stages

Stages 1–3 form the **engine**, which runs once per image (`src/crackgraph/engine.py`). Stages 4–5 work on its one result.

1. **Binarize** the micrograph with a global Otsu threshold (`binarize.py`).
2. **Skeletonize** (homotopy-preserving thinning) and prune dead ends shorter than about the largest agglomerate size (`skeleton.py`).
   - **Flaking exclusion** (`flaking.py`), using the skeleton's width map: some samples (seen so far on membrane-substrate T2/T3/T4) have patches where the catalyst layer has physically flaked off, exposing substrate. They're bright under Otsu like a crack, but they're missing material, not a fracture, and there's no evidence what crack pattern (if any) existed under them. Pixels far wider than the image's own typical crack width are grown back out to their true boundary, and every skeleton segment with a pixel inside that region is left out of every measurement, including the connectivity graph, so nothing connects through a flaked patch. Width is the only identification criterion, deliberately: a solidity-based second criterion was tried and dropped after it excluded a confirmed real (elongated) delamination case. A "smooth the boundary to look natural" approach was considered and rejected, because it shapes the output rather than measuring anything. See `docs/walkthrough/03_flaking.md`.
3. **Extract the crack graph**: nodes, segments, and the full pixel path of every segment (`graph.py`).
4. **Choose regions**: the whole image, its centre, or chosen cells of a grid (`regions.py`). A region only selects part of the one engine result, so every region is measured with the same threshold and flaking reference.
5. **Measure each region** (`measures/`): crack stats, tortuosity/curvature, anisotropy, and optionally a per-segment table. Pixel quantities count the pixels inside the region; segment quantities give each segment whole to the region holding its middle pixel; connectivity is whole-image only, because cutting the network at a region border splits it.

All stages draw on off-the-shelf image-processing libraries (scikit-image, skan); the code around them chooses settings, removes artefacts and labels what each number is.

## Libraries

- `scikit-image` for threshold/skeleton/distance-transform.
- `Skan` (skeleton-analysis.org) for skeleton→branch-graph — does most of stage 2–3; distinguishes junctions/endpoints, flags cycles.
- `sknw` when per-edge pixel polylines in a NetworkX graph are wanted.
- `networkx` for the connectivity graph in the batch export (connected components, giant component).

## One tool, user-chosen settings

Until 2026-11-13 the analysis was three separate entry points: a whole-image crack-stats export, a per-image tool (top-left corner crop by default) for curvature and anisotropy, and a 2×2 spatial-overview figure. They ran the same engine separately and had drifted apart (for example in how flaked segments were removed). They're now one tool with one set of settings (`src/crackgraph/settings.py`), run from the GUI (`app.py`) or the command line (`src/analyze.py`). The old entry points are archived in the repository's `archive/thesis_export_old_entry_points_2026-11-13/`.

- **What the user sets**: µm per pixel, the regions, the measurements and crack-stats column groups, and the figures. Which engine settings to expose is still open.
- **Calibration and the physical thresholds**: the spur cut-off and the dark-speck limit are justified by agglomerate size, so they're stored in µm (9.15 µm) and µm² (48.3 µm²) and converted with the user's µm per pixel. At the thesis calibration (0.6098 µm/px) they're exactly the 15 px and 130 px the thesis numbers were computed with.
- **Reproducibility**: every results workbook has a `settings` sheet listing every setting used. With default settings, the whole-image crack stats equal the earlier exporter's exactly, checked on two real images and locked in by a test against its frozen output.
- **Why one engine pass, not one per region**: re-running on each crop would give each region its own Otsu threshold and flaking reference width, so regions would be measured differently and wouldn't add up to the whole image.

## Crack stats for the sibling `image_visualization` repo

- **Column reference**: every column, the evidence-level legend (measured/interpreted/calibrated) and the calibration factor's provenance live in `docs/batch_stats/crack_stats_schema.md`. Read that file rather than re-deriving any of it here.
- **Downstream consumer, stated explicitly**: `../image_visualization` ("figlib" in its own docs) is
  a sibling project, a figure-making toolkit over the same `all_pics/` source catalogue this repo's
  `data/raw/` is drawn from. It reads the crack-stats workbook via `figlib/crack_data.py` and never
  hand-edits it -- corrections happen here and get re-copied over there. Keep
  `docs/batch_stats/crack_stats_schema.md` honest about anything figlib's own code (`_sample_id()`,
  its `crack_levels_table` configs) already assumes, rather than duplicating figlib's own docs here.
- **`v1`/`v2` replicate convention**: a filename's `v#` is a physically distinct replicate capture of
  the same condition, not a document-revision number. Include every replicate that passes the
  scale-bar/size checks when choosing images, rather than one canonical image per condition. Consumers wanting per-condition statistics group rows by `image_filename` with
  the trailing `_mm######.jpg` index stripped, and average only where >=2 replicates exist (matching
  what figlib's own `crack_levels_table` figures already do).
- **Naming-convention caveat, when choosing images**: the `mm000000`/`mm000001` naming pattern does
  *not* reliably predict which file carries the burned-in blue scale bar -- check every candidate by
  eye (bottom-right corner crop) before including it. The tool itself doesn't look at names.

## Synthetic-pattern validation gallery

A visual, human-reviewable companion to the numeric-tolerance pytest suite (`tests/test_curvature.py`, `test_anisotropy.py`), not a replacement for it.

- **`scripts/validation/validation_gallery.py [--out-dir outputs/validation]`**: runs a fixed battery of 5 synthetic cases (`src/crackgraph/validation_cases.py`, covering 2 measurement methods) through the real pipeline, and compiles each case's overlay/rose image plus an expected-vs-measured table into one page (`src/crackgraph/validation_report.py`'s `render_validation_report`, in `outputs/validation/report.html`).
- Every tolerance used for a case's PASS/FAIL verdict is duplicated (with a cross-reference comment), not imported, from the corresponding `tests/test_*.py` constant — tests aren't a dependency of `src/`.
- One case exists specifically to show a known method limitation honestly rather than hide it: `anisotropy_orthogonal_blind_spot` (the 2nd-order orientation tensor reads an orthogonal grid as isotropic; only the rose histogram reveals the two peaks). It has no fabricated pass condition.
- Ground truth is not bundled into `synthetic.py`'s return value (image-only, matching every existing test file's convention) — each case function re-derives its own expected values from the same arguments it passes to the generator.

## Documentation map

This file is the technical/scientific reference. Other docs cover other audiences —
they're not duplicated here:

- `README.md` — setup, how to run the GUI and command line, and the repo layout.
- `GLOSSARY.md` — one-line definitions of the terms used in the code and docs (node, degree,
  segment, giant component, tortuosity, anisotropy).
- `CALIBRATION.md` — status table (🟢 derived / 🟡 empirical uncalibrated / 🔴 assumed) for
  every tunable constant, with file:line pointers.
- `docs/walkthrough/` — a page-by-page code walkthrough, including the rationale for each
  tunable constant and the design of `skeleton.py` and `flaking.py`.
- `docs/batch_stats/crack_stats_schema.md` — column-by-column reference for the crack-stats
  columns of a results workbook, including the region columns and the thesis-notation mapping.
- `docs/unified_analysis_status.md` — status of the 2026-11-13 merge into one tool.
- `docs/experimental/dynamic_tracking_hypothetical.md` — a design discussion (not implemented, not
  tested) on whether/how this pipeline could extend to in-situ drying video instead of static
  micrographs; `scripts/experimental/tracing_poc.py` is a throwaway, unintegrated proof-of-concept
  tied to one idea in it. Both are explicitly exploratory future-direction material, not part of the
  validated pipeline.
- `docs/reviews/` — point-in-time methodology/rigor review findings.

## Design principles

- Every claim-bearing output is traceable to what the method can actually support. This project uses an evidence-level discipline elsewhere in the thesis (`[measured]` / `[interpreted]` / `[speculated]` / `[cited]`) that carries into the code and console output — labeling what a number is, not just what it is called. E.g. "crack area fraction is `[measured]`; which segment owns a pixel inside a junction blob is `[interpreted]`."
- Deterministic, reproducible measurement is preferred over anything that "looks about right" — hand-tuned magic constants carry a stated justification (ideally tied to `h`), tracked in `CALIBRATION.md`.
- The tool stays honest about uncertainty: a number that depends on a modelling choice is labelled `[interpreted]` (e.g. per-segment area near junctions), and each region row says how many segments or samples its tortuosity and anisotropy rest on.

## Reference spine (for context, not to be re-derived in code)

Thin-film fracture mechanics behind the analysis: Beuth 1992 (plane-strain channelling, defines `g(α,β)`), Xia & Hutchinson 2000 (shear-lag model, exponential stress recovery, curvature/spiral results), Goehring 2012 (rectilinear→hexagonal crack-network evolution), Bohn, Pauchard & Couder 2005 (hierarchical crack patterns). The image work is homotopy-preserving skeletonisation plus planar graph extraction.

Anisotropy/curvature sidequest (see `crackgraph/anisotropy.py` and `crackgraph/curvature.py` docstrings for the full attribution): axial circular statistics and the doubled-angle construction — Mardia & Jupp, *Directional Statistics*, Wiley, 2000; Fisher, *Statistical Analysis of Circular Data*, Cambridge University Press, 1993 (the more common reference in earth-science fracture/joint-orientation work). The 2nd-order orientation tensor formalism (and its known insufficiency, motivating a 4th-order tensor) — Advani & Tucker, "The Use of Tensors to Describe and Predict Fiber Orientation in Short Fiber Composites", *Journal of Rheology*, 1987. Chord-angle/turning-angle discrete curvature estimation on digitized curves — Rosenfeld & Johnston, "Angle Detection on Digital Curves", *IEEE Transactions on Computers* C-22(9), 1973 (an alternative standard estimator, the 3-point circle fit / Menger curvature, was not used — chosen for consistency with the shared chord-based scan in `_chord_scan.py`, not for a documented accuracy advantage). Tortuosity (arc/chord) is a generic, uncredited-to-one-source geometric ratio, used with the same definition in crack-path roughness work (Bouchaud, "Scaling properties of cracks", *J. Phys.: Condens. Matter* 9, 4319, 1997), vascular tortuosity, and river sinuosity.

## Scope discipline

Main deliverable: reliable, comparable per-image crack statistics across the conditions — Rakelspalt settings, SSC vs LSC, substrate, humidity — with known biases measured and stated. Work that makes these numbers trustworthy and comparable comes first.
