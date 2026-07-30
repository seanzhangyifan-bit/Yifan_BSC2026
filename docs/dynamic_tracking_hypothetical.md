# In-situ video tracking: a hypothetical, not an implementation

**Nothing in this document is built or tested.** This is a design discussion that took place
across several turns, about whether/how this pipeline could analyze an in-situ drying video
(continuous frames of a catalyst layer as it dries and cracks) instead of one-shot static
micrographs, and what it would take to do that within a practical time budget. It is recorded
here for future reference, in case this direction is picked up later -- not as a status update on
work in progress.

## 1. The hypothetical and the time budget

20 minutes of video at ~500 frames/minute = 10,000 frames. Analyzing this overnight gives roughly
30,000 seconds total, i.e. a budget around 3 seconds/frame in the best case, with 10 seconds/frame
as a more realistic stretch goal.

## 2. Measured runtime baseline (real numbers, not estimates)

Per-stage timing was already instrumented in `scripts/export_crack_stats_v3.py`'s `compute_row()`
(`runtime_binarize_s`, `runtime_skeletonize_s`, `runtime_flaking_s`, `runtime_graph_extract_s`,
`runtime_stats_s`, `runtime_total_s`) and is available in `outputs/crack_stats_v3_batch_bcd.xlsx`
for the 19-image batch B/C/D run -- full 7300x7600px (~55.6 megapixel) static micrographs, not
video frames.

| Stage | Mean time | % of total |
|---|---|---|
| binarize (Otsu) | 2.1 s | 4.9% |
| **skeletonize** | **39.7 s** | **85.9%** |
| flaking exclusion | 2.1 s | 4.3% |
| graph extraction (Skan) | 0.04 s | 0.1% |
| stats | 0.6 s | 1.3% |
| **total** | **46.0 s** | |

`[measured]`. Skeletonize dominates by roughly 6:1 over everything else combined -- it is the
only stage worth budgeting carefully for the video hypothetical.

### Why skeletonize costs what it does

`skimage.morphology.skeletonize()` (Zhang-Suen thinning, used in `src/crackgraph/skeleton.py`) is
an iterative boundary-peeling algorithm. Per-iteration cost is roughly O(N_fg) (foreground pixel
count) in an efficient implementation. The number of iterations needed to converge is *not*
constant, though -- it is roughly the largest local half-width (in px) of any connected foreground
region, since thinning must erode from the boundary all the way to the centerline. So the honest
complexity is closer to:

**O(N_fg x w_max)**, where `w_max` is the thickest region's local half-width in pixels.

For genuinely crack-shaped input (thin lines, width ~2-20px), `w_max` is small and roughly
constant regardless of image size, so this behaves close to O(N_fg) in practice `[interpreted]`.
For a **thick, solid blob** -- a delaminated/flaking patch, or (relevant to the video case) an
undried wet region that hasn't cracked yet -- `w_max` scales with the blob's own radius, and since
a compact blob's area also scales with radius^2, the cost for that one blob alone is closer to
**O(radius^3)**: cubic, not linear. This is a measured, not just theoretical, effect in this
dataset -- flaking regions are why skeletonize dominates runtime so heavily.

`skan` (used for graph extraction) has no incremental/windowed API, and neither does
`skimage.morphology` (checked directly: `skan.Skeleton` always rebuilds from a full array;
`skimage.morphology` only exposes full-frame `skeletonize`/`thin`/`medial_axis`). Anything
incremental discussed below would be custom-built, not a library flag being missed.

### What this implies for the video case

At full 55.6-megapixel resolution, skeletonize alone costs ~40s -- far over even the 10s stretch
budget. A real video frame is very likely far lower resolution (a 1080p frame is ~2 megapixels,
~27x fewer pixels than this dataset). Naive linear extrapolation puts skeletonize at ~1.5s and
total pipeline time at ~2s/frame at that resolution -- comfortably inside a 10s budget, plausibly
near the 3s stretch goal `[speculated]`, **provided** frames don't contain large thick solid
blobs. That caveat is not minor for this specific case: early frames of an in-situ drying video,
before cracking starts, are plausibly one large, still-wet, thick foreground blob -- exactly the
pathological case where iteration count blows up with blob radius. Those early frames could be
disproportionately the slowest in the whole run, not the crack-dense late frames one might
naively expect to be worst-case.

## 3. The incremental-update hypothesis, reframed as graph operations

The pipeline already represents a crack pattern as a planar graph: nodes (junctions/endpoints),
edges (crack segments with a full pixel polyline each) -- see `CLAUDE.md`'s "Atoms: arcs, not
whole cracks". The key realization from this discussion: a video-tracking scheme only ever needs
to touch pixels at the *frontier* -- a new blob, an existing tip, an existing edge's width -- never
the whole frame. Every already-established node/edge from the previous frame just carries forward
as data. The three ways a crack pattern changes between frames map onto three graph operations:

- **Widening**: no topology change. Same nodes, same edges -- just re-sample the distance
  transform (`medial_radius`, already computed once per frame in `skeleton.py`) along the
  already-known path and update that edge's width attribute. Cheapest case, no re-tracing needed.
  One caveat: if widening is asymmetric (one wall retreats faster than the other), the true
  medial axis can drift laterally even though topology hasn't changed -- trusting an old
  centerline forever would quietly accumulate error; a periodic local re-skeletonize of a narrow
  band around the existing path would catch this.
- **Initiation**: a new small connected component (foreground pixels present now that weren't
  present in the previous frame, not touching any existing crack) is a self-contained little
  subgraph -- built once, then merged into the overall graph like any other edge. One gap: a new
  crack can nucleate *touching* an existing one (no gap), in which case it isn't a disconnected
  blob at all and needs to be handled as an edge-splice on an existing edge (the propagation case
  below), not an initiation.
- **Propagation**: extending one specific existing edge's polyline outward from its degree-1 tip
  node. Three possible outcomes, each a specific graph operation: (a) the trace reaches a new
  zero-width pixel -- same edge, longer polyline, tip node just moves outward; (b) the trace finds
  a fork (two exit directions) -- that point becomes a new node, the old edge terminates there,
  two new child edges continue; (c) the trace runs into pixels belonging to an *already-existing
  separate* edge -- the growing crack has physically met another crack, a new junction node is
  inserted at the contact point (splitting the host edge it hit), and the growing edge connects
  into it.

Outcome (c) is worth pausing on, because it directly upgrades this project's core methodology
(see below, Sec. 5) -- not just a performance detail.

## 4. Prior art surveyed

- **General "dirty rectangle" / ROI-restricted incremental thinning**: the standard idiom from
  graphics/video processing -- diff the new frame against the last mask, connected-component-label
  the delta, only recompute inside a padded bbox around each changed region. Not crack-specific,
  but directly applicable to the initiation case above.
- **Fatigue crack-tip tracking (DIC)**: an active, established field -- but a different sensing
  modality than this project's images. Digital image correlation (DIC) tracks a loaded, speckled
  specimen's **displacement/strain field**, and locates the crack tip as where that field's
  mechanical signature (a stress-singularity / CTOD fit, or increasingly a CNN trained on the
  displacement field) terminates. This project's images are unloaded, backlit optical crack
  patterns with no displacement field to exploit -- the specific DIC techniques don't transfer,
  only the general framing does (separate "detect the tip precisely" from "track it forward
  without re-deriving from scratch"). Recent work in this space: CNN-based tip detection from DIC
  displacement fields (Nature Scientific Reports, 2022), CNN crack-path+tip detection (Fatigue &
  Fracture of Engineering Materials & Structures, 2021), a symbolic-regression-discovered
  iterative tip-correction formula (International Journal of Fatigue, 2024), and real-time 2D DIC
  crack-propagation tracing systems reporting ~5um resolution (Engineering Fracture Mechanics,
  2022) -- see conversation for full links.
- **Steger's curvilinear ridge tracing** (*"An Unbiased Detector of Curvilinear Structures,"* IEEE
  TPAMI 20(2), 1998): the classical answer to "trace a line structure point by point, robustly."
  Builds the local Hessian (2nd derivatives) of the intensity profile at each point; the
  eigenvector with the larger-magnitude eigenvalue points *across* the line, the other eigenvector
  points *along* it. A point is a true (subpixel) line point if the first derivative along the
  across-line eigenvector is zero there; tracing steps along the along-line eigenvector and
  re-locates the next true point, terminating where the line signature fades into background.

### Why naive greedy "step to the neighbor with the highest local radius" fails

An early version of the propagation idea proposed tracing from a known node by stepping to
whichever neighboring pixel has the largest distance-to-background (`medial_radius`) value, until
reaching a pixel with radius zero (surrounded by background = a tip). This fails for three
concrete reasons, all stemming from the same root cause -- a scalar magnitude cannot encode
direction:

1. **Wrong-way pull near a real tip**: `medial_radius` shrinks toward zero as a crack narrows to
   its tip. Stepping toward the *highest* value walks *away* from the tip, back toward the
   widest part of the crack already known -- directly backward from the goal.
2. **No forward signal on a uniform-width stretch**: along a straight crack of steady width,
   `medial_radius` is nearly flat in the along-crack direction and only rises/falls across the
   width. Pixel-level quantization/mask raggedness means neighbors can tie or the "highest" one
   is a pixel or two off-center, causing a greedy trace to zigzag across the crack width instead
   of advancing along it.
3. **No branch-selection signal at a junction**: `medial_radius` is large right at a junction
   simply because that's the widest point geometrically. A magnitude-only rule has no way to
   know which of several outgoing branches continues "the same crack."

## 5. A no-matrix alternative to Steger's method

Steger's method solves the direction problem with a Hessian eigen-decomposition. An equivalent
result, without matrices, was worked out as: run a local **smoothness-costed path search** (e.g.
Dijkstra/A*-style, not single-step-greedy) from the current tip toward the nearest zero-radius
pixel, where the cost is **local curvature of the radius profile along the candidate path**
(a second-difference-like term), not the raw magnitude of change (`|delta radius|`). This
distinction matters: a genuine, gradually tapering crack approaching its own tip has a *steady*,
predictable change in radius -- that's the expected signature of a real tip, not noise, and
should score as cheap. An *erratic*, unpredictable wiggle in radius (a sign of having wandered off
the true ridge) should score as expensive. Penalizing raw magnitude of change would wrongly
penalize legitimate tapering; penalizing curvature/erraticness does not.

Multi-step path search (rather than single-step greedy) also directly fixes failure mode 2 above
-- a single noisy pixel can no longer derail the whole trace, since the cost is evaluated
cumulatively over many steps.

Junction/fork detection under this scheme reuses machinery this project already has, rather than
needing anything new: the **annulus technique** already used for junction-angle measurement
(`CLAUDE.md`, stage 4) -- sample a small ring around the current tracing point and count distinct
angular sectors with foreground extending outward. One sector = keep tracing single-path. Two or
more = a real fork, and the correct behavior is to spawn a separate trace per sector, not to pick
a single "best" one (there often isn't a single correct branch at a genuine Y-split -- there are
two, and both are real).

## 6. The epistemic point (why this matters beyond performance)

This ties directly back to `CLAUDE.md`'s core framing: a single static micrograph has no external
timestamps, so a T-junction only certifies a *local* fact (the abutting crack arrived after the
crack it hit, *at that point*) -- the reconstructed partial order's incompleteness is a measured
result of that limitation, not a failure.

Propagation outcome (c) above -- the growing trace colliding with an already-existing separate
edge -- is not just a graph-update detail. It is *literally watching a T-junction form*, frame by
frame, with a real timestamp. In a video where this is caught on camera, the ordering between the
two cracks stops being an inference from junction geometry and becomes a directly observed fact.
This would upgrade the reconstructed partial order toward a directly-observed (near-)total order
for every junction caught forming on camera -- and it would turn the three existing chronometers
(junction angle, approach curvature, crack width) from primary evidence into a **validation check
against real ground truth**, rather than the only evidence available. That is a genuine epistemic
upgrade the static-image methodology cannot offer by construction, not merely a speed optimization.
