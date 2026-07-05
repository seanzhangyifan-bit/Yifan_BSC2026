# crack-project

Analysis tool for crack patterns in PEMFC catalyst-layer micrographs (BSc
thesis, KIT Thin Film Technology group). Full scientific and architectural
context — why the goal is a *partial order* of crack growth rather than a
full chronology, the pipeline's six stages, library choices, evidence-level
discipline — lives in [`CLAUDE.md`](./CLAUDE.md). Read that first; this file
is just setup/usage plus the current implementation status.

## Pipeline status

| Stage | What it does | Status |
|---|---|---|
| 1 | Binarize (threshold) | **Implemented** |
| 2 | Skeletonize + prune spurs | **Implemented** |
| 3 | Extract attributed planar graph (skan) | **Implemented** |
| 4 | Annulus angle measurement, T-vs-Y classification | **Implemented** |
| 5 | Precedence graph → transitive closure → DAG/cycle check | Not built |
| 6 | Width `w` (Dilworth/König), junction census, generation counts | Not built |

**What you get right now:** a skeleton, a planar graph, and every
degree-3 junction classified as T, Y, or ambiguous via the annulus angle
method (see below). For each T-junction, the abutter arc and the two host
arcs are identified. Degree-4+ junctions are counted but never classified
(the annulus method is only defined for a clean 3-way star). **There is
still no partial order/poset yet** — that needs stage 5 to assemble these
per-junction T/Y facts into an actual precedence graph with transitive
closure and cycle checking, which hasn't been built. Don't mistake the
current overlay/report for the thesis's actual finding; it's a
junction-geometry checkpoint, one step short of the ordering result.

### How junction angles are measured (stage 4)

Real crack edges are curved, so "the angle at a junction" is only
meaningful as a *local* quantity, measured right where the crack meets
another one — not by the edge's average direction over its whole length,
which would reflect wherever the crack happened to curve to further away.
But the pixels immediately at a junction vertex are also the least
trustworthy: skeletonization (thinning) is at its jitteriest exactly at
branch points, and where several thick strokes merge the junction "blob"
itself can be wider than a fixed jitter margin. The fix is an **annulus**
(a "donut" region) around each vertex: an *effective* inner radius —
`max(--annulus-inner-px, local crack half-width at the vertex)`, the
half-width coming from a distance transform of the mask (`skeleton.py`,
`medial_radius`) — that skips both the jitter and the merge blob, and an
outer radius bounding how far out the arm is sampled.

Within that band, each arm's direction is measured by a **tangent fit**,
not by simple averaging: the band pixels are fitted (unconstrained, not
anchored at the vertex pixel — that pixel sits inside the merge blob and
anchoring there biases every arm's direction) as a quadratic in arc length,
and the direction is the fitted curve's derivative at the vertex end.
This matters because real cracks are curved — a straight chord across a
curved arm points off to the side of where the crack is actually heading
at the junction (measured on real micrographs: a genuinely through-going
curved host read as ~150° instead of ~180° through chords, misfiling true
T-junctions as ambiguous). The same fit yields each arm's signed
**curvature** at the vertex as a by-product — groundwork for the
approach-curvature chronometer in CLAUDE.md. Arms too short to support a
stable curvature term automatically degrade to a line fit (`fit_degree`
records which was used).

**Window choice is measured, not asserted.** The outer radius trades off
two failure modes: too short, and pixel-level wobble dominates the fitted
tangent; too long (relative to how much the real crack curves), and the
fit is biased by curvature the window shouldn't be seeing. `scripts/
window_sweep.py` makes this trade-off concrete: it generates synthetic
T-junctions (straight hosts at 60/90/120°, curved hosts at radius 30/60 px)
with reproducible, seeded pixel-level wobble, runs them through the actual
production pipeline, and reports the bias/std/RMSE of the recovered
bearing against the known ground truth, for every (geometry, jitter,
window) combination. The shipped default is the window with the best
worst-case (minimax) RMSE across everything tested — see the table in
`ANNULUS_OUTER_PX_PLACEHOLDER`'s comment in `junctions.py` (reproduced by
re-running the script). This is still an uncalibrated placeholder (no
real `h`/µm-per-px exists yet) but it is no longer just an eyeballed guess.

**Angles are reported as signed bearings and sector gaps, not unsigned
pairwise angles.** An earlier version compared each pair of arm directions
with `arccos` (always in [0°, 180°]) — which silently folds any reflex
angle back into an acute-looking number and does not sum to 360° across
the three arms, discarding real geometric information (verified: a
junction with true sector gaps {83.5°, 74.2°, 202.5°} was being reported
as {83.5°, 74.2°, 157.5°}, which sums to 315°, not 360°). Every junction
now gets a signed **bearing** per arm and the three **sector gaps** between
them (sorted by bearing, wrapped around the circle) — these sum to
exactly 360° by construction and correctly show a reflex gap as reflex.
Classification is phrased the same way as before, just on gaps instead of
angles: two ~90° gaps plus one ~180° gap (the empty side between the host
arms) is a **T** (a real precedence fact: abutter arrived after the host);
three ~120° gaps is a **Y** (concurrent growth, no ordering signal);
anything else is **ambiguous** (also no signal, but counted, never
dropped).

**What the overlay draws, and what it doesn't claim.** For every
classified junction: a cyan curve shows the fitted quadratic/line
evaluated *only* over the band of pixels actually used (no extrapolation
past it), so any visible gap between that curve and the green skeleton is
a real, inspectable fit-quality signal rather than something the renderer
hides; a short cyan tick at the inner end shows the derived tangent
direction, deliberately drawn short so it isn't mistaken for a claim about
geometry beyond the fitted band. The dashed grey segment nearest the
vertex is the part of each arm's skeleton *inside* the effective inner
radius — i.e. inside the merged-stroke blob — labeled "not evidence"
because the skeleton there reflects the blob's shape, not any one arm's
true path (this directly addresses a review concern: the abutter's drawn
line otherwise looks like it continues into the host as an observed fact,
when the final stretch is a medial-axis artifact of the merge).

### Corner cross-check (independent of the skeleton entirely)

The tangent-fit method above measures the skeleton's medial axis — a
1px-wide idealization that is least stable exactly where it matters most,
at the junction blob where thick strokes merge. There's a second, entirely
independent way to read the same angle: the **background** (intact-film)
tiles between cracks. Where an abutter crack meets a host, the abutter's
finite width visibly notches the host-side tile into two separate tiles,
each with a sharp corner right at the meeting point — found via
`skimage.measure.find_contours` on the inverted mask. That corner's two
wall directions are a direct measurement of the crack directions there,
with no annulus and no junction-blob problem (though NOT immune to
curvature bias either — each wall direction is still a chord over a fixed
window, so a severely curved host still biases it, exactly like the
tangent fit; measured directly in `scripts/corner_window_sweep.py`).

Two corner counts are handled: exactly 2 (a T's notch — host/abutter
bearings disambiguated via the corner-to-corner direction) and exactly 3
(a Y's triple point — each corner's bearings matched against the closest
bearing from a different corner). Any other count, or bearings that don't
consistently pair up, is left **unresolved** rather than guessed at.

This is a **cross-check, not a replacement** (a deliberate choice): both
methods run, both get reported, and where they disagree that disagreement
is logged, not smoothed over — matching CLAUDE.md's own philosophy that
independent chronometers (angle, curvature, width) agreeing or disagreeing
is itself a validation signal that needs no ground truth. Confirmed live
on the real image: node 1212 in the T5 corner crop reads "ambiguous" from
the tangent fit (a 204.9° reflex gap, just past tolerance) but resolves
cleanly to "T" from the corner method (166.1° gap) — a genuine, useful
disagreement worth a human look, not a bug in either method.

The corner window (`--corner-window-px`) is justified the same
measured way as the annulus radius —
`python3 scripts/corner_window_sweep.py` sweeps window size against known
synthetic geometry and picks the choice with the best combined worst-case
RMSE *and* worst-case unresolved-fraction (a small window that "resolves"
cleanly on easy cases but fails to find corners at all under jitter isn't
actually better).

### Kink flagging (suspected fused cracks)

A sharp direction change in the *interior* of an edge — far from any
junction — suggests two distinct cracks got fused into one skeleton path
(e.g. one crack runs out of frame and another comes in, meeting at a sharp
corner that is a degree-2 point, so no junction node exists there). The
kink scan walks every edge polyline and flags interior points where the
direction changes by more than a threshold over a small window. Flags are
**report/overlay only**: topology is deliberately unchanged, and actually
splitting flagged edges into two arcs is deferred to a later task (it
changes what stage 5 will treat as the atoms of the partial order).

**Region of interest:** for now, every run analyzes only a fixed top-left
corner crop of the input image (12.5% of image width per side, inset 2% of
width from the true corner), not the full image. This is a deliberate,
temporary scope limit while stage 1-3 correctness is being validated on a
small, fast, eyeball-able region and while staying clear of the true image
edges (any border/vignetting artifacts). Pass `--full-image` to bypass it —
untested so far, but the code path exists so it isn't a dead end later.

## Setup

```
source .venv/bin/activate    # already provisioned with skimage, skan, sknw,
                              # networkx, numpy, scipy, matplotlib, Pillow, pytest
```

## Running the pipeline

From the repo root:

```
python3 -m src.analyze_image data/raw/T5/T5-M_H95_v1_mm000001.jpg
```

This binarizes, skeletonizes+prunes, and extracts the graph for the default
corner crop, prints a labeled report to the console, and saves an overlay
PNG to `outputs/`.

### CLI flags

| Flag | Default | Meaning |
|---|---|---|
| `--out-dir` | `outputs` | where the overlay PNG is written |
| `--spur-px` | `15` | **[placeholder]** spur-length threshold in pixels, not derived from a calibrated film thickness `h` or µm/px (neither exists yet — calibration will be supplied manually later) |
| `--min-object-px` | `4` | pre-skeletonize despeckle size (kills JPEG block-noise specks; too small to erode real crack width) |
| `--max-overlay-dim` | `2500` | cap on the saved overlay's longest side (analysis itself always runs at full resolution of the region processed; only the saved image is downsampled) |
| `--otsu-sanity-band` | `0.01 0.15` | plausible foreground-fraction range; outside it, the report prints a `[WARNING]` rather than silently trusting the Otsu threshold |
| `--corner-frac` | `0.125` | corner-crop size, as a fraction of image width |
| `--edge-margin-frac` | `0.02` | inset from the true top-left corner, as a fraction of image width |
| `--full-image` | off | bypass the corner crop and process the whole image (not exercised yet) |
| `--annulus-inner-px` | `5.0` | **[placeholder]** inner annulus radius (px) — floor for the effective inner radius; widened per-junction to the local crack half-width where that's larger (see below). Not derived from calibrated µm/px |
| `--annulus-outer-px` | `60.0` | **[placeholder]** outer annulus radius (px). CLAUDE.md's general spec is `~h/2` but no film-thickness calibration exists yet. Chosen from `scripts/window_sweep.py`'s measured minimax RMSE (see "How junction angles are measured"), not eyeballed — still in documented tension with the "local, not far-field" intent; revisit when `h` is calibrated |
| `--y-angle-tol-deg` | `15.0` | **[placeholder]** tolerance around 120° for a Y classification |
| `--t-straight-tol-deg` | `20.0` | **[placeholder]** tolerance around 180° for accepting two arms as the host pair of a T |
| `--t-right-tol-deg` | `20.0` | **[placeholder]** tolerance around 90° for accepting the third arm as the abutter of a T |
| `--kink-window-px` | `10.0` | **[placeholder]** chord window (px of arc length) on each side of a candidate interior kink point |
| `--kink-turn-deg` | `45.0` | **[placeholder]** minimum interior direction change to flag as a kink (suspected two fused cracks) |
| `--corner-search-radius-px` | `25.0` | **[placeholder]** how far from a junction vertex to search background contours for wall corners |
| `--corner-window-px` | `10.0` | **[placeholder]** chord window for each wall's direction at a candidate corner; chosen from `scripts/corner_window_sweep.py`'s measured sweep |
| `--corner-min-turn-deg` | `45.0` | **[placeholder]** minimum turning angle to accept a contour point as a real wall corner |
| `--show-fit-detail` | off | also write a second, detailed overlay (see below); the default overlay is always written regardless |

### Output

- Console report: a **Parameters** block first, echoing every CLI flag
  value used (all placeholders included) plus the numpy/skimage/skan
  versions, so the report is reproducible from its own header alone; then
  threshold + foreground fraction (stage 1), skeleton pixel counts
  pre/post-prune + spur/fragment counts (stage 2), node/edge counts broken
  down by degree (stage 3), per-junction T/Y/ambiguous/insufficient-data
  counts and a full per-junction listing with sector gaps (labeled with
  their sum, which is always 360) and host curvature (stage 4), the
  kink scan's flag list, and the corner cross-check's agree/disagree/
  unresolved breakdown with a per-junction listing flagging disagreements.
  Every number is labeled `[measured]`, `[interpreted]`, or `[placeholder]`
  per the evidence-level discipline in CLAUDE.md.
- **Two overlay views**, since "does this look right" and "audit the angle
  estimator" want different amounts of information on screen (an earlier
  single-view design put everything on one image, including a legend drawn
  *inside* the axes that regularly covered real junctions):
  - `outputs/{image_stem}_corner_overlay.png` (always written; `_full_overlay.png`
    with `--full-image`): the clean quick-look view — skeleton in green,
    endpoints (degree 1) in orange, degree-3 junctions colored by
    classification (T = blue triangle, Y = green plus, ambiguous = orange x,
    insufficient annulus data = gray x), degree ≥ 4 junctions (unclassified)
    in red, flagged kinks as magenta stars, detected wall corners (gold
    diamonds) from the independent corner cross-check — outlined in red
    with a red ring around the junction vertex wherever the two methods
    disagree — and a short label (the `node_id`, cross-referencing the
    console report) at each classified junction.
  - `outputs/{image_stem}_corner_overlay_detail.png` (only with
    `--show-fit-detail`): everything above, plus the fitted-curve
    diagnostics — a cyan curve (the fitted tangent model, drawn only over
    the band it was fitted to), a short cyan tick (the derived direction),
    a dashed grey segment (the part of the skeleton inside the junction
    blob, labeled "not evidence") — and the label switches to the full
    three sector-gap values instead of just the ID.
  - The legend is drawn **below** both images (`bbox_to_anchor` with a
    negative y-offset), never on top of image content. Labels for
    junctions closer together than a small threshold cycle through
    increasingly-offset placements (with a white-outlined background box)
    rather than colliding — this resolves small local clusters but a
    handful of junctions within a few pixels of each other will still look
    busy; that's a real density limit in the data, not a layout bug.

### Reproducibility

The pipeline itself has no randomness anywhere (binarize/skeletonize/
extract/classify/kink-scan are all deterministic given the same image and
flags) — the only place randomness appears is in the synthetic test-image
generators' optional `jitter_px` (used to simulate skeletonization wobble
for the estimator sweep), and that's always seeded (`rng_seed`) so it's
reproducible too. Combined with the Parameters block above, any console
report fully specifies how to regenerate it: same image, same flags, same
library versions, same output.

## Verifying it works

Two checks, in order — no full-image run yet (see above):

1. **Synthetic correctness check** (known ground truth):
   ```
   python3 -m pytest tests/ -v
   ```
   `test_synthetic.py` renders a minimal image with exactly one T-junction
   and asserts the pipeline recovers exactly 1 junction (degree 3), 3
   endpoints, and 3 edges — validates the full stage 1-3 chain against a
   case with a known right answer, not just "runs without crashing."
   `test_junction_angle.py` goes further and checks a known **angle**, not
   just topology: synthetic T-junctions at 90° and at an off-right angle
   (75°), a T-junction whose host is a circular arc of known radius (the
   regression case for the tangent-fit estimator: a chord-based estimate
   provably misfiles it as ambiguous, and the measured curvature must match
   1/radius with opposite signs on the two host arms), a synthetic
   Y-junction (120° arms), a deliberately-ambiguous 3-way junction
   (60°/120°/180° arms — must NOT be forced into T or Y), and a
   deliberately-too-short abutter (must be flagged `insufficient_data`,
   not crashed or silently guessed); a thick synthetic T checks that
   supplying `medial_radius` widens the effective inner radius past the
   junction blob. `test_kinks.py` checks the kink scan against a bent line
   with a known corner (exactly one flag, at the right place, with the
   right turn angle) and against straight geometry (zero flags).
   `test_corners.py` checks the independent corner cross-check the same
   way: straight T's at 90°/75° (exactly 2 corners, correct bearings,
   agrees with the tangent fit), a Y-junction (exactly 3 corners), the
   same ambiguous case (must not be forced either), a gently-curved host
   (should resolve cleanly), and a short/thin arm (must fail gracefully
   with `label=None`, not a crash or a guess).

2. **Window-choice justification** (deterministic, seeded):
   ```
   python3 scripts/window_sweep.py
   python3 scripts/corner_window_sweep.py
   ```
   Print the bias/std/RMSE tables (per geometry/jitter/window) that
   `ANNULUS_OUTER_PX_PLACEHOLDER` and `CORNER_WINDOW_PX` are set from —
   re-run after changing the radii, jitter model, or fit method, and
   update the constants' comments if the recommendation changes.

3. **Real-image corner crop, visual check**:
   ```
   python3 -m src.analyze_image data/raw/T5/T5-M_H95_v1_mm000001.jpg --show-fit-detail
   ```
   then open `outputs/T5-M_H95_v1_mm000001_corner_overlay.png` (clean view)
   and confirm by eye that markers sit at actual junctions/tips and any
   red-ringed disagreements between the tangent-fit and corner methods
   look like genuinely ambiguous/borderline geometry (not an obvious bug
   in one or the other); then open `..._corner_overlay_detail.png` and
   confirm the cyan fitted curves hug the green skeleton (not diverge
   from it).

## Repo layout

```
src/
  crackgraph/
    io_utils.py    # image loading
    region.py      # default top-left corner crop selection
    binarize.py    # stage 1
    skeleton.py    # stage 2 (skeletonize + iterative spur pruning via skan; also EDT medial_radius)
    graph.py       # stage 3 (skan graph extraction, degree-based classification)
    junctions.py   # stage 4 (annulus tangent-fit bearings/sector-gap classification)
    kinks.py       # flag-only interior-corner (fused-crack) detection
    corners.py     # independent cross-check: background-tile wall-corner angles
    overlay.py     # overlay PNG rendering
    synthetic.py   # synthetic junction/kink test-image generators (known ground truth, seeded jitter)
  analyze_image.py # CLI entry point
scripts/
  window_sweep.py        # deterministic bias/std/RMSE sweep justifying the annulus outer radius
  corner_window_sweep.py # same, for the corner cross-check's window
tests/
  test_synthetic.py
  test_junction_angle.py
  test_kinks.py
  test_corners.py
```
