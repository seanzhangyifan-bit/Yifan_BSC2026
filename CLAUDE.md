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
2. Skeletonise (homotopy-preserving thinning). Prune spurs/hairs shorter than ~film-thickness equivalent.
3. Extract attributed planar graph: nodes, edges, and **the full pixel polyline per edge** (needed for angle/curvature/width).
4. Measure per junction on an **annulus** around the vertex: inner radius a few px (skeleton jitter near vertices is severe), outer radius ~h/2 (local approach direction, not far-field). Classify T vs Y; for each T emit `abutter ≺ host`.
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
