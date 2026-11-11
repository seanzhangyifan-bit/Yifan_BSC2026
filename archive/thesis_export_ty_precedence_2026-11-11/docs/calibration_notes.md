# Calibration notes

Full rationale for every constant listed in [`CALIBRATION.md`](../CALIBRATION.md), relocated
verbatim from what used to be each constant's inline comment. Nothing here is reworded or
summarized — if a constant's justification changes, update it here (and re-run the
referenced sweep script), not just the one-line pointer left in the source file.

## ANNULUS_INNER_PX_PLACEHOLDER

`src/crackgraph/junctions.py:77` — value `5.0`

> "a few px" per METHODOLOGY.md's own wording for stage 4, chosen to sit outside the pixel
> cluster where skeletonization jitter right at a vertex is worst. Not derived from
> calibrated um-per-px (none exists yet -- same project-phase caveat as
> SPUR_PX_PLACEHOLDER in skeleton.py). Revisit once calibration lands.

Not swept by either `scripts/validation/window_sweep.py` or `scripts/validation/corner_window_sweep.py` — both
hold `INNER_RADIUS_PX = 5.0` fixed while sweeping other parameters. No dedicated
inner-radius sweep exists.

## ANNULUS_OUTER_PX_PLACEHOLDER

`src/crackgraph/junctions.py:79` — value `60.0`

> Not derived from real film thickness h (METHODOLOGY.md's general spec is "~h/2"; no
> h/um-per-px exists yet) -- in documented tension with METHODOLOGY.md's "local approach
> direction, not far-field" intent, and cannot be checked against h until calibration
> lands.
>
> Chosen from a measured bias/variance/RMSE sweep (scripts/validation/window_sweep.py,
> deterministic/seeded), not asserted. Worst-case (minimax) RMSE of recovered arm bearing
> vs ground truth, across straight T's at 60/90/120 deg and curved-host T's at radius
> 30/60 px, at jitter levels 0/0.5/1.0 px (smooth, spatially-correlated synthetic wobble
> -- see _smooth_jitter_1d in synthetic.py):
>
> ```
> outer_radius_px=20: worst-case RMSE = 20.4 deg
> outer_radius_px=30: worst-case RMSE = 17.1 deg
> outer_radius_px=40: worst-case RMSE = 10.5 deg
> outer_radius_px=60: worst-case RMSE =  9.7 deg  <- minimax choice
> outer_radius_px=80: worst-case RMSE =  9.7 deg  (no further gain --
>                      the tested arm lengths are already fully used)
> ```
>
> Short arms are automatically fitted over whatever length they have (see fit_degree)
> rather than failing outright. Re-run the sweep and update this comment if the
> geometry/jitter grid changes.

Also referenced in `junctions.py`'s module docstring: "...so the default window is long
(~60 px, see ANNULUS_OUTER_PX_PLACEHOLDER) and short bands degrade to a line fit rather
than an unstable quadratic (see fit_degree)."

`scripts/validation/window_sweep.py` docstring: "Justify ANNULUS_OUTER_PX_PLACEHOLDER (junctions.py)
with a measured bias/variance/RMSE sweep, instead of asserting a window length from a
single eyeballed census." Sweeps `WINDOWS = [20.0, 30.0, 40.0, 60.0, 80.0]`,
`JITTER_LEVELS = [0.0, 0.5, 1.0]`, `N_SEEDS_WHEN_JITTERED = 6`, over straight-T geometries
(60/90/120 deg) and curved-T geometries (radius 30/60), using
`generate_t_junction`/`generate_curved_t_junction` from `src/crackgraph/synthetic.py`.
Runs the real pipeline end to end and prints `Recommended ANNULUS_OUTER_PX_PLACEHOLDER =
{best_window:.0f}`.

`tests/test_junction_angle.py`'s `test_default_window_recovers_bearing_under_jitter`:
"Locks in the ANNULUS_OUTER_PX_PLACEHOLDER=60 choice (justified by
scripts/validation/window_sweep.py's measured bias/variance/RMSE sweep) as a regression test:
fixed-seed jittered synthetics, at the shipped default annulus radii, must still recover
each arm's known bearing within the sweep's measured worst-case RMSE ballpark (~10 deg),
generously rounded up for single-sample (not aggregate) margin."

## QUAD_MIN_SPAN_PX

`src/crackgraph/junctions.py:81` — value `15.0`

> Minimum arc-length span of band points for the quadratic (curvature) term to have
> enough lever arm; below this the fit degrades to a line (a short arm cannot reveal its
> curvature reliably anyway).

No sweep script or dedicated test references this constant by name; used at
`junctions.py` in the band/fit-degree decision (`if n_in_band >= 6 and span >=
QUAD_MIN_SPAN_PX:`).

## Y_ANGLE_TOL_DEG_PLACEHOLDER

`src/crackgraph/junctions.py:83` — value `15.0`

> Generous enough to absorb skeleton-pixel jitter plus the natural angle spread of real
> desiccation Y-junctions around the ideal 120 deg, tight enough to stay diagnostic. Not
> fitted to a noise model; revisit once measured-angle histograms exist for real images.

No dedicated sweep script. Used as the default in `cross_check_junctions`; passed
explicitly as `y_angle_tol_deg=15.0` in `tests/test_corners.py`.

## T_STRAIGHT_TOL_DEG_PLACEHOLDER

`src/crackgraph/junctions.py:85` — value `20.0`

> tolerance on how collinear the two candidate host arms must be (pairwise angle near
> 180 deg) before they're accepted as "the host".

No dedicated sweep script. Used explicitly in `tests/test_corners.py`
(`t_straight_tol_deg=20.0`).

## T_RIGHT_TOL_DEG_PLACEHOLDER

`src/crackgraph/junctions.py:87` — value `20.0`

> tolerance on how close to 90 deg the abutter's approach to each host arm must be.

No dedicated sweep script. Used explicitly in `tests/test_corners.py`
(`t_right_tol_deg=20.0`), and echoed in `src/analyze_image.py`'s console report string.

## CORNER_SEARCH_RADIUS_PX

`src/crackgraph/corners.py:58` — value `25.0`

> how far from a junction vertex to look for background-tile corners. Must comfortably
> exceed typical crack half-width (the T notch's corner separation) so both notch corners
> are found; not yet tied to a calibrated h.

Held fixed (not swept) in `scripts/validation/corner_window_sweep.py` (`SEARCH_RADIUS_PX = 25.0`) —
that script sweeps `CORNER_WINDOW_PX`, not this constant. No dedicated search-radius
sweep exists.

## CORNER_WINDOW_PX

`src/crackgraph/corners.py:60` — value `10.0`

> chord half-window (arc length) used to measure each wall's direction on either side of
> a candidate corner point. Chosen from scripts/validation/corner_window_sweep.py's measured sweep
> (straight T's at 60/90/120 deg, curved-host T's at radius 30/60 px, jitter 0/0.5/1.0
> px), scoring each window by worst-case RMSE *and* worst-case unresolved fraction
> together (a small window that "resolves" cleanly on the easy cases but fails to find
> corners at all under jitter is not actually better). Summary at window=10: worst-case
> RMSE 15.6 deg, worst-case unresolved 38% (both driven by the jitter=1.0 px cells;
> jitter=0 cells resolve 100% with RMSE well under 5 deg at this window). Re-run the
> script and update this comment if the geometry/jitter grid changes.

Also referenced in `corners.py`'s module docstring: "This does NOT make the method immune
to curvature bias, though: each wall direction is still a chord over CORNER_WINDOW_PX, so
a severely curved host wall biases it exactly the way a too-long annulus window biased
the tangent fit (measured directly: scripts/validation/corner_window_sweep.py's radius=30 px cases
show real bias at the window chosen for jitter robustness). The advantage over the
tangent fit is narrower and specific: no junction-blob/skeleton-jitter problem, not a
general cure for curvature-vs-window tradeoffs."

`scripts/validation/corner_window_sweep.py` docstring: "Justify CORNER_WINDOW_PX (corners.py) with a
measured bias/variance/RMSE sweep, the same method used for
ANNULUS_OUTER_PX_PLACEHOLDER (scripts/validation/window_sweep.py) -- not an eyeballed guess." Sweeps
`WINDOWS = [3.0, 4.0, 6.0, 8.0, 10.0, 12.0]` across the same geometry/jitter grid,
additionally tracking a "resolution rate" (fraction of junctions where corner
count/pairing produced an answer), combining `combined = worst_rmse +
100*worst_unresolved` to choose the window; prints `Recommended CORNER_WINDOW_PX =
{best_window:.0f}`.

`tests/test_corners.py`: "Looser than the tangent-fit's own recovery tolerance -- the
corner window (CORNER_WINDOW_PX) is a first-pass default, not yet set from a measured
sweep the way ANNULUS_OUTER_PX_PLACEHOLDER was." And in
`test_curved_host_resolves_cleanly`: "Wall corners avoid the medial-axis junction-blob
problem, but they are NOT immune to a bias-vs-window tradeoff on curved hosts either (the
corner_window_sweep measured this directly): a corner window long enough to be
jitter-robust (CORNER_WINDOW_PX=10, chosen for that reason) still averages over enough of
a *severely* curved wall to bias the angle. radius=30 (the default, deliberately extreme
-- it was chosen to stress-test the OLD tangent-fit chord method's small window) does NOT
resolve cleanly at this window; radius=60 (a gentler, more typical curve) does. Both
facts are honest and measured -- this test asserts the case that should work, not the
hardest case there is."

## CORNER_MIN_TURN_DEG

`src/crackgraph/corners.py:62` — value `45.0`

> minimum turning angle (a chord-based turning-angle scan) to accept a contour
> point as a real wall corner rather than boundary noise. Not calibrated.

Held fixed (not swept) in `scripts/validation/corner_window_sweep.py` (`MIN_TURN_DEG = 45.0`). No
dedicated sweep for this specific constant.

## ABUTTER_AGREEMENT_TOL_DEG

`src/crackgraph/corners.py:64` — value `30.0`

> in the T-like (2-corner) case, the two corners' independent estimates of the abutter's
> bearing must agree within this tolerance or the pairing is treated as inconsistent
> (unresolvable) rather than silently averaged.

No dedicated sweep script or explicit test override found; used at `corners.py`'s
agreement check (`if abs(_angle_diff(abutter_a, abutter_b)) > ABUTTER_AGREEMENT_TOL_DEG:`).

## BEARING_MATCH_TOL_DEG

`src/crackgraph/corners.py:66` — value `30.0`

> in the Y-like (3-corner) case, the greedy bearing-matching used to pair up the 6 raw
> wall bearings into 3 arm bearings requires the matched pair to agree within this
> tolerance; otherwise unresolvable.

No dedicated sweep script found; used at `corners.py`'s bearing-matching step
(`if best_j is None or best_diff > BEARING_MATCH_TOL_DEG:`).

## SPUR_PX_PLACEHOLDER

`src/crackgraph/skeleton.py:24` — value `15`

**Physical justification (added 2026-11-11, after the fact).** The value was chosen before
any of this was known; it was then checked against measured length scales and found to
match them. It was not re-derived or changed.

- **Scale.** 15 px × 0.6098 µm/px = **9.1 µm** (calibration for `mm` mosaic images only; see
  `docs/batch_stats/crack_stats_schema.md` §6).
- **Agglomerate size** `[measured]`. Laser diffraction of the wet inks
  (`../image_visualization/data/Auswertung_PGV_v1.xlsx`, read via figlib's `psd_data.py`):
  d90 = 7.7–7.9 µm and d99 ≈ 7–10 µm for inks T2–T4; T1 d90 = 4.2 µm; T5 d90 = 1.3 µm with a
  ~2 vol% tail above 10 µm.
- **Film thickness** `[measured]` (`../image_visualization/data/Schichten_Charakterisierung.xlsx`):
  mostly 8–16 µm; the thin T5 height-variation series is 3–6 µm.
- **Argument** `[interpreted]`. Agglomerates of this size make the crack walls rough on the
  same scale, and thinning turns wall bumps into short dead ends. A dead end shorter than
  about one large agglomerate (or one film thickness) can't be told apart from wall
  roughness, so it isn't counted as a crack.

**Caveats.**
- The PSD is of diluted wet ink; agglomerates may re-form during drying. It is the best
  available proxy for agglomerate size in the dried layer, not a direct measurement of it.
- One cut-off is used for every image on purpose. The physical scales differ between inks
  and coatings, and a per-condition cut-off would make conditions measured differently.
- The argument covers spurs (wall bumps), not fragments: removed fragments on thin-crack
  images are mostly pieces of real faint cracks broken up by thresholding.
- `ledge` depends strongly on this cut-off (on six 2048 px crops, `ledge` rises 50% on
  T3-PTFE_v1 between no cut-off and 15 px), so it must be reported together with `ledge`.

Original note, kept for history:

> Not derived from real film-thickness h or a calibrated um-per-pixel value -- neither
> exists yet (calibration is supplied manually, later). Chosen only as "somewhat larger
> than the annulus inner-radius jitter scale (a few px)" that METHODOLOGY.md mentions
> elsewhere, so as to not eat real short branches. Must be revisited once calibration
> lands.

No sweep script targets this constant. Note that in both `scripts/validation/window_sweep.py` and
`scripts/validation/corner_window_sweep.py`, and in essentially all synthetic tests
(`tests/test_junction_angle.py`, `tests/test_corners.py`), the
pipeline is invoked with `spur_px=3` (an override, not the placeholder default) — i.e.
the sweep/test harnesses deliberately bypass this constant's default value rather than
validating it.

## DARK_SPECK_AREA_PX

`src/crackgraph/skeleton.py:30` — value `130` (was `HOLE_AREA_THRESHOLD_PX2` = `50` until 2026-11-11)

Dark specks inside a crack (pieces of catalyst layer or dust sitting in the gap) smaller than this
many px are removed right after bright spots are filled (`remove_small_objects`) and before
`skeletonize()`. A speck left in makes the skeleton loop around it, adding two junctions and
short edges.

**Physical justification.** 130 px × (0.6098 µm/px)² = **48 µm²**, the area of a circle of
diameter ≈ 7.8 µm: the d90 agglomerate size of inks T2–T4 `[measured]` (same PSD source as
`SPUR_PX_PLACEHOLDER` above). A dark speck no bigger than one agglomerate inside a crack is
read as material sitting in the gap, not a separate crack cell `[interpreted]`. Same caveats
as above: wet-ink PSD, one value for every image, `mm` images only.

**Measured effect of 50 → 130 px** (2048 px centre crops of 6 micrographs,
`outputs/hole_fill_test/`): 14 real specks inside cracks newly removed (plus 5 dark background
slivers cut off at the crop edge), removing their loops; `ledge` +0.9 to +6.9% on the four crops with specks,
`wcrack`, crack area and `N` unchanged.

The old 50 px value was carried over from an informal prototype script and never derived.

## Removed: CORR_THRESHOLD and MIN_LEN_FOR_CORR_PX

Removed 2026-11-11 with the correlation-based corner test they belonged to (0.99, 🟡, a 4-point
hand sweep on one image; and 4 px, 🔴). The host-stub rule that replaced the test uses
`SPUR_PX_PLACEHOLDER` and adds no constant of its own. Why the test was replaced:
`docs/design_notes.md`, skeleton.py section.

## CORNER_TO_TANGENT_BEARING_TOL_DEG

`src/crackgraph/precedence.py:59` — value `45.0`

> how far apart the corner method's and the tangent-fit's independent bearing estimates
> for the same arm may be and still be treated as "the same arm" when recovering
> path_index identity for a corner-only claim. Deliberately generous (these are two
> geometrically distinct measurements, not two readings of the same fit) but not yet
> measured via a sweep the way ANNULUS_OUTER_PX_PLACEHOLDER/CORNER_WINDOW_PX were --
> revisit once real disagreement-rate data exists (see corner cross-check report).

Self-documented as not yet swept. No test file references it directly by name.
