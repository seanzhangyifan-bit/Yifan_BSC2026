# How much do the T/Y junction counts depend on the angle cut-offs?

- **Date**: 2026-11-11
- **Script**: [`scripts/validation/junction_tolerance_sweep.py`](../scripts/validation/junction_tolerance_sweep.py)
- **Data**: the 41 images the batch exporter selects from `data/raw/` (23 conditions, 21 with at least
  one measurable junction), top-left corner crop, flaking excluded, every other setting at its
  default. This is the same pipeline as `src/analyze_image.py`.
- **Reproduce**: `python3 -m scripts.validation.junction_tolerance_sweep --data-dir ../data/raw`
  (about 4 minutes).

## Why this was checked

The pipeline labels each 3-way junction by its three angles: T (about 90°/90°/180°), Y (about
120°/120°/120°), or ambiguous. Three cut-offs decide how close is close enough:

| Cut-off | Default | Meaning |
|---|---|---|
| `Y_ANGLE_TOL_DEG_PLACEHOLDER` | ±15° | every angle within this of 120° → Y |
| `T_STRAIGHT_TOL_DEG_PLACEHOLDER` | ±20° | largest angle within this of 180° … |
| `T_RIGHT_TOL_DEG_PLACEHOLDER` | ±20° | … and the other two within this of 90° → T |

All three are 🔴 assumed in [`CALIBRATION.md`](../CALIBRATION.md). The junction census is a
headline result, so this checks how much it moves when the cut-offs move. Changing a cut-off
doesn't change any measured angle, so each image's angles were measured once and then re-sorted
under every setting.

## Results

### At the current cut-offs, most junctions are ambiguous `[measured]`

Of 1,135 junctions whose angles could be measured: **291 T (26%), 81 Y (7%), 763 ambiguous
(67%)**. Another 140 couldn't be measured (`insufficient_data`), and none of the cut-offs affect
those.

The ambiguous junctions aren't measurement failures. In a sample of 243, the median angles were
**84° / 118° / 156°**, between a T and a Y. Only 7% had an angle below 45°, the kind of value a
broken measurement would give. `[measured]`

### Absolute counts depend strongly on the cut-offs `[measured]`

| Setting | T | Y | Ambiguous | T share* |
|---|---|---|---|---|
| All cut-offs × 0.5 | 103 | 17 | 1015 | 9% |
| All cut-offs × 0.75 | 196 | 46 | 893 | 17% |
| **Current (15° / 20° / 20°)** | **291** | **81** | **763** | **26%** |
| All cut-offs × 1.25 | 410 | 123 | 602 | 36% |
| All cut-offs × 1.5 | 510 | 169 | 456 | 45% |

\*T share = T / (T + Y + ambiguous).

Moving one cut-off by ±5° alone moves the T share by roughly 3–7 percentage points. The Y count
is the most fragile: from 6 (Y cut-off ±5°) to 208 (±25°), without changing anything else.

### Ranking conditions against each other is more stable `[measured]`

This compares each setting's ranking of conditions by T share against the current ranking, using
Spearman rank correlation (1.0 = identical order).

| Change from current | Rank correlation |
|---|---|
| T straight cut-off ±5° | 0.98 |
| T right-angle cut-off ±5° | 0.84–0.95 |
| All cut-offs × 0.75 / × 1.25 | 0.82 / 0.93 |
| All cut-offs × 0.5 / × 1.5 | 0.48 / 0.91 |
| Y cut-off, any value 5–25° | 1.00 (Y doesn't enter T share) |

### Sample sizes are small in the corner crop `[measured]`

Conditions have a median of 24 measurable junctions, and six have 11 or fewer (T1-N_PTFE and
0RH_PTFE have none). Across the tested settings, a condition's T share moves by up to 0.80.

## What this means

- **Don't report absolute T/Y counts or T share as fixed numbers.** They depend on a hand-picked
  cut-off about as much as on the sample. If you report them, show them at more than one cut-off
  or state the range. `[interpreted]`
- **Comparing conditions is more defensible than absolute values.** Rank order holds well for
  ±5° / ±25% changes. Check that any specific comparison you report keeps its direction across
  this range: the per-condition CSV has every setting. `[interpreted]`
- **A Y count on its own isn't reportable.** It swings 35-fold across plausible cut-offs.
  `[interpreted]`
- **T vs Y looks like a continuum in this data, not two clean groups.** Two-thirds of junctions
  sit between the templates. A continuous measure, such as the largest angle per junction, may
  describe the data better than a two-way count. This is consistent with gradual T→Y evolution
  in drying crack networks (Goehring 2012), but this check doesn't test that. `[speculated]`

## Limits of this check

- Corner crop only, so samples per condition are small and per-condition numbers are noisy. A
  full-image run (`--full-image`) would give far more junctions, but full-image junction
  classification hasn't been validated yet (see `METHODOLOGY.md`).
- This tests sensitivity, not correctness. It shows how much the answer depends on the cut-offs,
  not which cut-offs are right. The cut-offs stay 🔴 assumed.
- Conditions are grouped by filename with the replicate tag removed. Which conditions form the
  SSC-vs-LSC and gap-height comparisons hasn't been decided here.
