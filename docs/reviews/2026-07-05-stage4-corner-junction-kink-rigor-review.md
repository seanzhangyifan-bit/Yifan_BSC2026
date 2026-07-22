# Rigor review: stage 4 corner/junction/kink estimation

- **Date**: 2026-07-05
- **Reviewer**: `scientific-rigor` subagent (see `.claude/agents/scientific-rigor.md`), run against the working tree
- **Scope**: uncommitted changes on top of `78dbd06` — `README.md`; `src/analyze_image.py`; `src/crackgraph/{corners,junctions,kinks,overlay,skeleton,synthetic}.py`; `scripts/`; `tests/test_{corners,junction_angle,kinks}.py`
- **Status of these findings**: not yet fixed. This is a record for the next reviewer (human or agent) to pick up before the corner/junction cross-check ships in a thesis-facing result.

## Findings

### 1. [Overclaim] `EdgeDirection` fields labeled `[measured]` are actually extrapolated model output, not raw pixel measurement

`src/crackgraph/junctions.py:131-134` labels `direction`, `bearing_deg`, `curvature_per_px` as `[measured]`. The module's own docstring (lines 29-34) states the tangent is "the fitted derivative at s = 0 ... extrapolated back from the band" — the band explicitly excludes points near the vertex (jitter/blob exclusion), so s=0 is *outside* the region the polynomial was actually fit over. This is a modeled quantity, not a direct pixel readout — closer to CLAUDE.md's "interpreted" tier. Tellingly, `overlay.py:243-259` is more careful: in detail mode it deliberately draws the fitted curve only over the actually-fitted band, "so what is drawn IS what was measured" — while the classification pipeline uses the extrapolated s=0 value under a `[measured]` tag.

**Fix**: relabel these fields (e.g. `[measured; extrapolated tangent-fit value, see _edge_direction docstring]`) so a reader can't mistake curve-fit output for a raw observation.

### 2. [Unacknowledged-disagreement] The corner-vs-tangent-fit cross-check never validates which arm is the abutter — most load-bearing finding

`src/crackgraph/corners.py:318-324`:
```python
agrees = label == jc.label
corner_sorted = sorted(gaps)
tangent_sorted = sorted(jc.sector_gaps_deg)
max_disagreement = max(abs(a - b) for a, b in zip(corner_sorted, tangent_sorted))
```
`agrees_with_tangent_fit` only compares the T/Y/ambiguous label string, and `max_gap_disagreement_deg` compares *sorted* gap magnitudes — both discard which physical arm was identified as the abutter. `_pair_t_like` (corners.py:202-229) does compute an ordered `[host_a, host_b, abutter_bearing]`, but that identity is discarded before reaching `CornerCrossCheck` — there's no field comparing it to `jc.abutter_path_index`/`jc.host_path_indices`.

Concrete failure scenario: two methods could both say "T" with near-identical sorted gap sets, yet the corner method's abutter could correspond to a *different physical arm* than the tangent-fit's abutter. The current code would report this as "Agree," even though the underlying precedence claim (`abutter ≺ host` — the actual thing CLAUDE.md cares about) disagrees between methods. This is the "compare summary statistics, not the actual claim" failure the disagreement-logging discipline is supposed to prevent.

**Fix**: add arm-identity matching (nearest-bearing correspondence between the corner method's 3 arm bearings and the tangent-fit's 3 `EdgeDirection.bearing_deg` values) and report agreement/disagreement on *which arm is abutter*, not just on the label.

### 3. [Missing-justification] `QUAD_MIN_SPAN_PX = 15.0` gates the curvature chronometer with no measured backing

`src/crackgraph/junctions.py:108-111`. This threshold decides `fit_degree` (2 vs 1), i.e. whether curvature — one of CLAUDE.md's three named chronometers — is computed at all for a given arm. Unlike `ANNULUS_OUTER_PX_PLACEHOLDER` and `CORNER_WINDOW_PX`, which got dedicated sweep scripts (`scripts/window_sweep.py`, `scripts/corner_window_sweep.py`) with printed bias/RMSE tables, this constant has only a qualitative justification ("a short arm cannot reveal its curvature reliably anyway").

**Fix**: give it the same measured-sweep treatment now that the sweep infrastructure already exists.

### 4. [Missing-justification] Classification-boundary tolerances that determine the headline T/Y/ambiguous census are un-swept placeholders

`Y_ANGLE_TOL_DEG_PLACEHOLDER`, `T_STRAIGHT_TOL_DEG_PLACEHOLDER`, `T_RIGHT_TOL_DEG_PLACEHOLDER` (junctions.py:113-125), plus `CORNER_MIN_TURN_DEG`, `ABUTTER_AGREEMENT_TOL_DEG`, `BEARING_MATCH_TOL_DEG` (corners.py:77-91) are honestly commented as "not calibrated" / "not fitted to a noise model." CLAUDE.md names "junction-type census" as a headline floor deliverable, and that census's T-vs-Y split hinges entirely on these thresholds.

**Fix**: same measured-sweep treatment as the window radii, before census numbers go in the thesis.

### 5. [Unsupported-assumption] Corner-pairing's only separation guard is a numerical-coincidence check, not a physical-scale one

`src/crackgraph/corners.py:202-211`, `_pair_t_like` guards only `np.linalg.norm(d_ab) < 1e-6` before trusting the corner-to-corner direction (`bearing_ab`) as a proxy for the host-wall direction. If two corners of a T-notch are genuinely close together (thin/short abutter, or search-radius edge effects), `bearing_ab` could be dominated by pixel noise while still clearing 1e-6 — yet the code proceeds to disambiguate host/abutter from it rather than abstaining. There's no minimum-separation floor tied to a physical scale (e.g. expected crack thickness), unlike the annulus/kink windows which at least gesture toward `h`.

**Fix**: add `MIN_CORNER_SEPARATION_PX` (ideally tied to expected abutter thickness) that returns "unresolved" below it.

### 6. [Nit / reproducibility] Several "verified"/"measured directly"/"observed on real micrographs" docstring claims cite specific numbers with no runnable artifact behind them

E.g. junctions.py:28 ("observed on real micrographs... reads ~145-160 deg"), junctions.py:56-58 ("verified on real data: a junction with true sector gaps {83.5, 74.2, 202.3}..."), junctions.py:40 ("anchoring biases the direction (verified)"). These are plausibly genuine findings from prior debugging (consistent with earlier synthetic + corner-crop + overlay verification work), but unlike the window-radius sweeps, they aren't captured as a script or regression-test fixture a reader can re-run.

**Fix**: low severity — capture as a regression test or sweep script if/when convenient, for symmetry with the rest of the codebase's show-your-work habit.

## Verdict

This change **preserves** the partial-order/evidence discipline overall: no chronology is fabricated, degree≥4 junctions and near-120° ambiguity correctly abstain rather than guess, kinks are flagged not merged, disagreement is (mostly) surfaced rather than smoothed, and randomness is seeded/reproducible throughout.

**The single most load-bearing fix is finding 2**: make the corner-cross-check's agreement metric compare arm identity (which arm is abutter), not just the coarse T/Y/ambiguous label and sorted gap magnitudes — as written, the one cross-check meant to validate the actual `abutter ≺ host` precedence claim cannot detect the one disagreement mode that would matter for stage 5.
