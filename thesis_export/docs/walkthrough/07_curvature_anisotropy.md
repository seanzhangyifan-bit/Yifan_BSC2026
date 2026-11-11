# 7. Curvature and anisotropy

**Files**:
- `src/crackgraph/curvature.py` (247 lines)
- `src/crackgraph/anisotropy.py` (266 lines)
- `src/crackgraph/_chord_scan.py` (55 lines)

Two **shape** measurements of the network. They say nothing about which crack came first.

- **Curvature / tortuosity**: how bent each segment is.
- **Anisotropy**: whether the cracks tend to point in one direction (grid-like) or every
  direction (mud-crack-like).

Both rely on one small shared technique, the **chord-pair scan**.

---

## `_chord_scan.py`: the shared technique

Smooth out pixel staircasing by measuring direction over a short stretch rather than
pixel-to-pixel.

| Function | Line | What it does |
|---|---|---|
| `arc_length(coords)` | 11 | Running distance along a path: 0 at the start, adding each step's length. |
| `chord_pair_at(coords, s, k, window_px)` | 17 | At point `k`, the straight line ("chord") from `window_px` *behind* to `k`, and from `k` to `window_px` *ahead*. Returns `None` if there isn't room on both sides. |

The angle between the incoming and outgoing chord is how much the path **turns** at `k`.

---

## `curvature.py`: how bent is each segment?

**Two numbers per segment**, because they catch different things:
- **Tortuosity** = path length ÷ straight-line distance between the ends. 1.0 = perfectly
  straight. Whole-segment, and doesn't depend on any window setting.
- **Curvature profile**: at each point, the turn angle ÷ the distance it happens over (units:
  1/px; 1/curvature = the radius of the bend). The mean and max are reported.

A gentle long bend and a few sharp kinks can share a tortuosity but have very different
curvature, so both are kept.

### Settings, lines 60–88 (comments sit *below* each)

| Setting | Value | Meaning |
|---|---|---|
| `CURVATURE_WINDOW_PX_PLACEHOLDER` | 10 px | Chord length on each side. Chosen by `scripts/validation/curvature_window_sweep.py`. |
| `CHORD_LENGTH_EPS_PX` | 1 px | Ends closer than this → no tortuosity (dividing by nearly zero). |
| `TORTUOSITY_MIN_CHORD_PX_PLACEHOLDER` | 10 px | Segments shorter than this are left out of **summary stats and plots**. Their tortuosity is real but dominated by pixel staircasing at the ends. |

### `reliable_tortuosities(...)`, line 116

The *one* place the "long enough" filter is applied, so the spreadsheet and the plots can't
disagree.

### `compute_edge_curvature(skel, graph_result, window_px)`, line 128

For each segment:
1. **Lines 183–192**: path length and straight-line length → tortuosity, or `None` if the ends
   nearly touch.
2. **Lines 199–224**: if the segment is at least 2 windows long, scan every interior point with
   `chord_pair_at`, convert the turn angle to curvature, and keep the mean and max.

**Why turn ÷ (span / 2)?** On a circle, the chord from `s − w` to `s` is parallel to the circle's
direction at the chord's midpoint, `s − w/2`. So the two chords' angle is the turn over a
distance of about `w`, not `2w`. The comment at lines 144–153 explains it.

**Limitation (lines 35–49).** On a perfect circle the window choice doesn't bias the result. On
real cracks, whose bend changes along their length, a bigger window blurs nearby bends together.
The sweep only tests circles, so it covers the noise side of that tradeoff, not the blur side.

---

## `anisotropy.py`: do the cracks share a direction?

**The idea.** Collect every crack's direction, weighted by length. Ask whether they cluster
around one direction.

**The trick: "axial" directions.** A crack at 10° and one at 190° are the same line, so averaging
them as arrows would cancel them out. Doubling every angle first maps 10° and 190° to 20° and
380° = 20°, the same arrow. Then average.

```
C = weighted mean of cos(2θ),  S = weighted mean of sin(2θ)
A = √(C² + S²)                  0 = no preferred direction, 1 = all parallel
dominant direction = ½ · atan2(S, C)
```

This is the standard 2nd-order **orientation tensor** from fracture and fibre analysis
(references in the file's opening comment, lines 30–45).

**Known blind spot (lines 47–63).** A perfect grid, half the cracks at 0° and half at 90°, gives
A = 0, the same as random directions. Doubled, 0° and 90° become 0° and 180°, which cancel. So
the **rose histogram is a required companion**: only it shows two peaks.

### Functions

| Function | Line | What it does |
|---|---|---|
| `anisotropy_index_from_bearings(bearings, weights)` | 111 | The formula above. Pure maths, tested directly against known answers. |
| `compute_orientation_samples(...)` | 134 | Direction samples from every segment. Long segments: one sample per interior point, with direction = the sum of the incoming and outgoing chord directions, which smooths the 45° pixel steps. Short segments: one end-to-end sample, weighted by length. |
| `compute_anisotropy(...)` | 218 | Combine all samples: A, dominant direction, and an 18-bin histogram (10° bins) for the rose plot. |

The verbal labels ("grid-like" ≥ 0.5, "mud-crack-like" < 0.15) live in `xlsx_report.py` and are
`[interpreted]`. Always read them next to the histogram.

---

## Worth knowing

- **Both work on the corner crop by default** (inside `analyze_image.py`). The spatial overview
  runs them on whole images and quadrants (page 9).
- **Tests**:
  - `tests/test_curvature.py` (7 tests): straight arms, a known circular arc, a sharp kink,
    short segments, and degenerate segments.
  - `tests/test_anisotropy.py` (7 tests): all-parallel, random, orthogonal grid (the blind
    spot), and histogram consistency.
