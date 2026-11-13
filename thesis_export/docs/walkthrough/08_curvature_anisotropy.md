# 8. Curvature, tortuosity and anisotropy

**Files**:
- `src/crackgraph/curvature.py` (241 lines), `src/crackgraph/measures/tortuosity.py` (50 lines)
- `src/crackgraph/anisotropy.py` (206 lines), `src/crackgraph/measures/anisotropy.py` (33 lines)
- `src/crackgraph/_chord_scan.py` (34 lines)

Two shape measurements:
- **Curvature / tortuosity**: how bent each segment is.
- **Anisotropy**: a rose plot of crack directions.

Both use the **chord-pair scan**. `curvature.py` and `anisotropy.py` hold the methods; `measures/`
runs them once per image and reports per region.

---

## `_chord_scan.py`: the shared technique

Measures direction over a short stretch, not pixel to pixel, to smooth pixel staircasing.

| Function | Line | What it does |
|---|---|---|
| `arc_length(coords)` | 11 | Running distance along a path. |
| `chord_pair_at(coords, s, k, window_px)` | 17 | The chords from `window_px` behind point `k` to `k`, and from `k` to `window_px` ahead. `None` if there's no room. |

The angle between the two chords is how much the path turns at `k`.

---

## `curvature.py`: how bent is each segment?

- **Tortuosity** = path length ÷ straight-line distance between the ends. 1.0 = straight. No
  window setting involved.
- **Curvature**: turn angle ÷ distance, at each point (1/px; 1/curvature = bend radius). Mean and
  max are reported.

A long gentle bend and a few sharp kinks can share a tortuosity, so both are kept.

### Settings, lines 60–88 (comments below each)

| Setting | Value | Meaning |
|---|---|---|
| `CURVATURE_WINDOW_PX_PLACEHOLDER` | 10 px | Chord length each side. From `scripts/validation/curvature_window_sweep.py`. |
| `CHORD_LENGTH_EPS_PX` | 1 px | Ends closer than this: no tortuosity. |
| `TORTUOSITY_MIN_CHORD_PX_PLACEHOLDER` | 10 px | Shorter segments are left out of summaries and plots: their tortuosity is dominated by staircasing at the ends. |

### `reliable_tortuosities(...)`, line 116

The one place the "long enough" filter is applied, so tables and plots agree.

### `compute_edge_curvature(skel, graph_result, window_px)`, line 128

Per segment:
1. Lines 183–192: tortuosity, or `None` if the ends nearly touch.
2. Lines 199–224: if at least 2 windows long, scan each interior point, convert the turn angle to
   curvature, keep mean and max.

- **Why turn ÷ (span / 2)?** On a circle, each chord is parallel to the curve at its midpoint, so
  the two chords' angle is the turn over about `w`, not `2w` (comment at lines 144–153).
- **Limitation (lines 35–49).** A bigger window blurs nearby bends on real cracks. The sweep only
  tests circles, so it covers noise, not blur.

---

## `anisotropy.py`: which way do the cracks point?

- Every segment is sampled along its length; each sample has a direction and a length weight.
- Directions are **axial**: 10° and 190° are the same crack, so all directions fold into 0–180°.
- The result is an 18-bin histogram (10° bins), drawn as a **rose plot**, mirrored onto both
  halves of the circle.
- **No single index is reported.** A one-number index (the 2nd-order orientation tensor) reads an
  equal-weight orthogonal grid as random directions. Only the histogram shows the two peaks.

| Function | Line | What it does |
|---|---|---|
| `compute_orientation_samples(...)` | 60 | Samples from every segment, each with its image position. Long segments: one per interior point, direction = sum of the two chord directions (smooths 45° pixel steps). Short segments: one end-to-end sample. |
| `compute_anisotropy(...)` | 148 | Samples from every segment, then `anisotropy_from_samples`. |
| `anisotropy_from_samples(samples)` | 162 | The weighted histogram from a set of samples, so a region can use only its own. |
| `share_near(result, bearing)` | 197 | Share of the length within ±10° of a direction. Used by the tests and validation gallery. |

---

## Per region: `measures/`

One scan per image; each region uses its part. Flake-touching segments are left out.

| Function | File, line | What it does |
|---|---|---|
| `scan_curvature` | `tortuosity.py`, 18 | Curvature of every segment. |
| `curvature_in_region` | `tortuosity.py`, 24 | Keeps segments whose middle pixel is in the region (page 6). |
| `measure_tortuosity` | `tortuosity.py`, 33 | Columns: mean and median tortuosity, mean and max curvature (1/µm), segment counts. |
| `scan_orientations` | `anisotropy.py`, 16 | Direction samples along every kept segment. |
| `anisotropy_in_region` | `anisotropy.py`, 23 | Histogram of the samples inside the region (by sample position). |
| `measure_anisotropy` | `anisotropy.py`, 30 | Column: `anisotropy_n_samples`. The result itself is the rose plot (page 9). |

---

## Worth knowing

- Before 2026-11-13 the per-image tool rebuilt the graph after removing flaked segments, so older
  tortuosity and rose plots can differ slightly.
- Small regions have few segments: check `tortuosity_n_segments` and `anisotropy_n_samples`.
- **Tests**:
  - `tests/test_curvature.py` (7): straight arms, circular arc, sharp kink, short and degenerate
    segments.
  - `tests/test_anisotropy.py` (5): aligned field, random field, equal and unequal orthogonal
    grids, empty input. Tolerances from 8 seeds per field.
