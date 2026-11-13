# Calibration status of tunable constants

A heuristic: the colours summarise, by judgement, how each value was chosen. They are not a
measure of accuracy.

- 🟢 **derived**: matches a measured physical scale.
- 🟡 **empirical**: chosen by a synthetic sweep, not calibrated on real images.
- 🔴 **assumed**: no sweep or derivation yet.

| Constant | File:Line | Value | Status | Reason |
|-|-|-|-|-|
| `SPUR_PX_PLACEHOLDER` | [`skeleton.py:24`](src/crackgraph/skeleton.py) | 15 px | 🟢 (checked after choosing) | 15 px = 9.1 µm ≈ largest agglomerates (d99 of inks T2–T4, 7–10 µm) and film thickness (8–16 µm). Tests override it (`spur_px=3`). |
| `DARK_SPECK_AREA_PX` | [`skeleton.py:30`](src/crackgraph/skeleton.py) | 130 px | 🟢 | 130 px = 48 µm², area of a d90 ≈ 7.8 µm agglomerate (inks T2–T4). 50 px (🔴) before 2026-11-11. |
| `CURVATURE_WINDOW_PX_PLACEHOLDER` | [`curvature.py:60`](src/crackgraph/curvature.py) | 10 px | 🟡 | Minimax-RMSE sweep, `scripts/validation/curvature_window_sweep.py`. |
| `ORIENT_WINDOW_PX_PLACEHOLDER` | [`anisotropy.py:24`](src/crackgraph/anisotropy.py) | 10 px | 🔴 | Same scale as the curvature window; not swept. |
| `WIDTH_FLAG_MULTIPLIER_K` | [`flaking.py:31`](src/crackgraph/flaking.py) | 4.0 | 🔴 | Set on one image. |
| `MIN_CANDIDATE_AREA_PX` | [`flaking.py:35`](src/crackgraph/flaking.py) | 500 px | 🔴 | Set on one image. |
| `GROWTH_MULTIPLIER` | [`flaking.py:43`](src/crackgraph/flaking.py) | 2.2 | 🔴 | Set on one image. |
| `GROWTH_STEP_PX` | [`flaking.py:49`](src/crackgraph/flaking.py) | 3 px | 🔴 | Set on one image. |

**Net: 2 🟢, 1 🟡, 5 🔴.**

- The two 🟢 thresholds are px values at 0.6098 µm/px (`mm` images). The analysis stores them in
  µm (`SPUR_UM` = 9.15 µm, `DARK_SPECK_AREA_UM2` = 48.3 µm², `settings.py`) and converts them with
  the µm per pixel you set.
- Rationale for each constant: the walkthrough page for its module (`docs/walkthrough/`).
- Display-only constants (`MAX_PANEL_REGIONS`, `SKELETON_DILATE_PX`) are left out.
