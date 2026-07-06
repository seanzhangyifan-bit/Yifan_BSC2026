# Calibration notes

Full rationale for every constant listed in [`CALIBRATION.md`](../CALIBRATION.md), relocated
verbatim from what used to be each constant's inline comment. Nothing here is reworded or
summarized — if a constant's justification changes, update it here (and re-run the
referenced sweep script), not just the one-line pointer left in the source file.

## ANNULUS_INNER_PX_PLACEHOLDER

`src/crackgraph/junctions.py:77` — value `5.0`

> "a few px" per CLAUDE.md's own wording for stage 4, chosen to sit outside the pixel
> cluster where skeletonization jitter right at a vertex is worst. Not derived from
> calibrated um-per-px (none exists yet -- same project-phase caveat as
> SPUR_PX_PLACEHOLDER in skeleton.py). Revisit once calibration lands.

Not swept by either `scripts/window_sweep.py` or `scripts/corner_window_sweep.py` — both
hold `INNER_RADIUS_PX = 5.0` fixed while sweeping other parameters. No dedicated
inner-radius sweep exists.

## ANNULUS_OUTER_PX_PLACEHOLDER

`src/crackgraph/junctions.py:84` — value `60.0`

> Not derived from real film thickness h (CLAUDE.md's general spec is "~h/2"; no
> h/um-per-px exists yet) -- in documented tension with CLAUDE.md's "local approach
> direction, not far-field" intent, and cannot be checked against h until calibration
> lands.
>
> Chosen from a measured bias/variance/RMSE sweep (scripts/window_sweep.py,
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

`scripts/window_sweep.py` docstring: "Justify ANNULUS_OUTER_PX_PLACEHOLDER (junctions.py)
with a measured bias/variance/RMSE sweep, instead of asserting a window length from a
single eyeballed census." Sweeps `WINDOWS = [20.0, 30.0, 40.0, 60.0, 80.0]`,
`JITTER_LEVELS = [0.0, 0.5, 1.0]`, `N_SEEDS_WHEN_JITTERED = 6`, over straight-T geometries
(60/90/120 deg) and curved-T geometries (radius 30/60), using
`generate_t_junction`/`generate_curved_t_junction` from `src/crackgraph/synthetic.py`.
Runs the real pipeline end to end and prints `Recommended ANNULUS_OUTER_PX_PLACEHOLDER =
{best_window:.0f}`.

`tests/test_junction_angle.py`'s `test_default_window_recovers_bearing_under_jitter`:
"Locks in the ANNULUS_OUTER_PX_PLACEHOLDER=60 choice (justified by
scripts/window_sweep.py's measured bias/variance/RMSE sweep) as a regression test:
fixed-seed jittered synthetics, at the shipped default annulus radii, must still recover
each arm's known bearing within the sweep's measured worst-case RMSE ballpark (~10 deg),
generously rounded up for single-sample (not aggregate) margin."

## QUAD_MIN_SPAN_PX

`src/crackgraph/junctions.py:108` — value `15.0`

> Minimum arc-length span of band points for the quadratic (curvature) term to have
> enough lever arm; below this the fit degrades to a line (a short arm cannot reveal its
> curvature reliably anyway).

No sweep script or dedicated test references this constant by name; used at
`junctions.py` in the band/fit-degree decision (`if n_in_band >= 6 and span >=
QUAD_MIN_SPAN_PX:`).

## Y_ANGLE_TOL_DEG_PLACEHOLDER

`src/crackgraph/junctions.py:113` — value `15.0`

> Generous enough to absorb skeleton-pixel jitter plus the natural angle spread of real
> desiccation Y-junctions around the ideal 120 deg, tight enough to stay diagnostic. Not
> fitted to a noise model; revisit once measured-angle histograms exist for real images.

No dedicated sweep script. Used as the default in `cross_check_junctions`; passed
explicitly as `y_angle_tol_deg=15.0` in `tests/test_corners.py`.

## T_STRAIGHT_TOL_DEG_PLACEHOLDER

`src/crackgraph/junctions.py:119` — value `20.0`

> tolerance on how collinear the two candidate host arms must be (pairwise angle near
> 180 deg) before they're accepted as "the host".

No dedicated sweep script. Used explicitly in `tests/test_corners.py`
(`t_straight_tol_deg=20.0`).

## T_RIGHT_TOL_DEG_PLACEHOLDER

`src/crackgraph/junctions.py:123` — value `20.0`

> tolerance on how close to 90 deg the abutter's approach to each host arm must be.

No dedicated sweep script. Used explicitly in `tests/test_corners.py`
(`t_right_tol_deg=20.0`), and echoed in `src/analyze_image.py`'s console report string.

## CORNER_SEARCH_RADIUS_PX

`src/crackgraph/corners.py:58` — value `25.0`

> how far from a junction vertex to look for background-tile corners. Must comfortably
> exceed typical crack half-width (the T notch's corner separation) so both notch corners
> are found; not yet tied to a calibrated h.

Held fixed (not swept) in `scripts/corner_window_sweep.py` (`SEARCH_RADIUS_PX = 25.0`) —
that script sweeps `CORNER_WINDOW_PX`, not this constant. No dedicated search-radius
sweep exists.

## CORNER_WINDOW_PX

`src/crackgraph/corners.py:64` — value `10.0`

> chord half-window (arc length) used to measure each wall's direction on either side of
> a candidate corner point. Chosen from scripts/corner_window_sweep.py's measured sweep
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
the tangent fit (measured directly: scripts/corner_window_sweep.py's radius=30 px cases
show real bias at the window chosen for jitter robustness). The advantage over the
tangent fit is narrower and specific: no junction-blob/skeleton-jitter problem, not a
general cure for curvature-vs-window tradeoffs."

`scripts/corner_window_sweep.py` docstring: "Justify CORNER_WINDOW_PX (corners.py) with a
measured bias/variance/RMSE sweep, the same method used for
ANNULUS_OUTER_PX_PLACEHOLDER (scripts/window_sweep.py) -- not an eyeballed guess." Sweeps
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

`src/crackgraph/corners.py:77` — value `45.0`

> minimum turning angle (see kinks.py's identically-shaped scan) to accept a contour
> point as a real wall corner rather than boundary noise. Not calibrated.

Held fixed (not swept) in `scripts/corner_window_sweep.py` (`MIN_TURN_DEG = 45.0`). No
dedicated sweep for this specific constant.

## ABUTTER_AGREEMENT_TOL_DEG

`src/crackgraph/corners.py:82` — value `30.0`

> in the T-like (2-corner) case, the two corners' independent estimates of the abutter's
> bearing must agree within this tolerance or the pairing is treated as inconsistent
> (unresolvable) rather than silently averaged.

No dedicated sweep script or explicit test override found; used at `corners.py`'s
agreement check (`if abs(_angle_diff(abutter_a, abutter_b)) > ABUTTER_AGREEMENT_TOL_DEG:`).

## BEARING_MATCH_TOL_DEG

`src/crackgraph/corners.py:88` — value `30.0`

> in the Y-like (3-corner) case, the greedy bearing-matching used to pair up the 6 raw
> wall bearings into 3 arm bearings requires the matched pair to agree within this
> tolerance; otherwise unresolvable.

No dedicated sweep script found; used at `corners.py`'s bearing-matching step
(`if best_j is None or best_diff > BEARING_MATCH_TOL_DEG:`).

## SPUR_PX_PLACEHOLDER

`src/crackgraph/skeleton.py:22` — value `15`

> Not derived from real film-thickness h or a calibrated um-per-pixel value -- neither
> exists yet (calibration is supplied manually, later). Chosen only as "somewhat larger
> than the annulus inner-radius jitter scale (a few px)" that CLAUDE.md mentions
> elsewhere, so as to not eat real short branches. Must be revisited once calibration
> lands.

No sweep script targets this constant. Note that in both `scripts/window_sweep.py` and
`scripts/corner_window_sweep.py`, and in essentially all synthetic tests
(`tests/test_kinks.py`, `tests/test_junction_angle.py`, `tests/test_corners.py`), the
pipeline is invoked with `spur_px=3` (an override, not the placeholder default) — i.e.
the sweep/test harnesses deliberately bypass this constant's default value rather than
validating it.

## KINK_WINDOW_PX_PLACEHOLDER

`src/crackgraph/kinks.py:27` — value `10.0`

> chord window (arc length) on each side of a candidate point. Same jitter-averaging
> scale reasoning as the annulus radii in junctions.py; not derived from calibrated
> h/um-per-px (none exists yet).

No dedicated sweep script (unlike ANNULUS_OUTER_PX_PLACEHOLDER and CORNER_WINDOW_PX, each
of which has its own sweep script). Only exercised via `tests/test_kinks.py`'s
correctness tests, which check detection behavior, not this specific tolerance value.

## KINK_TURN_DEG_PLACEHOLDER

`src/crackgraph/kinks.py:32` — value `45.0`

> minimum direction change to flag. Must exceed what smooth crack curvature plausibly
> produces over ~2*window px, so that a flag means "probably two distinct cracks", not
> "curved crack". Not calibrated; revisit once measured turn-angle histograms exist for
> real images.

No `scripts/*sweep*.py` references this constant. `tests/test_kinks.py`'s
`test_kink_detected_at_known_corner` uses a `turn_deg=60.0` synthetic and asserts
`abs(kink.turn_angle_deg - 60.0) < 12.0`, with the comment: "60-deg turn at the image
center. Skeletonization rounds the apex over ~the line thickness, so the measured turn
reads a bit under the drawn 60 deg -- tolerance reflects that, it's not estimator slack."
This is a correctness check, not a calibration sweep of this constant itself.

## CORNER_TO_TANGENT_BEARING_TOL_DEG

`src/crackgraph/precedence.py:58` — value `45.0`

> how far apart the corner method's and the tangent-fit's independent bearing estimates
> for the same arm may be and still be treated as "the same arm" when recovering
> path_index identity for a corner-only claim. Deliberately generous (these are two
> geometrically distinct measurements, not two readings of the same fit) but not yet
> measured via a sweep the way ANNULUS_OUTER_PX_PLACEHOLDER/CORNER_WINDOW_PX were --
> revisit once real disagreement-rate data exists (see corner cross-check report).

Self-documented as not yet swept. No test file references it directly by name.
