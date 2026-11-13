# 8. Curvature, tortuosity and anisotropy

**Files**:
- `src/crackgraph/curvature.py` (241 lines) and `src/crackgraph/measures/tortuosity.py` (50 lines)
- `src/crackgraph/anisotropy.py` (280 lines) and `src/crackgraph/measures/anisotropy.py` (41 lines)
- `src/crackgraph/_chord_scan.py` (34 lines)

Two **shape** measurements of the network. They say nothing about which crack came first.

- **Curvature / tortuosity**: how bent each segment is.
- **Anisotropy**: whether the cracks tend to point in one direction (grid-like) or every
  direction (mud-crack-like).

Both rely on one small shared technique, the **chord-pair scan**. `curvature.py` and
`anisotropy.py` hold the methods; the two files in `measures/` run them once per image and
report them per region (end of this page).

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
| `anisotropy_index_from_bearings(bearings, weights)` | 113 | The formula above. Pure maths, tested directly against known answers. |
| `compute_orientation_samples(...)` | 136 | Direction samples from every segment, each with its position on the image. Long segments: one sample per interior point, with direction = the sum of the incoming and outgoing chord directions, which smooths the 45° pixel steps. Short segments: one end-to-end sample, weighted by length. |
| `compute_anisotropy(...)` | 224 | Samples from every segment, then `anisotropy_from_samples`. |
| `anisotropy_from_samples(samples)` | 238 | Combine a set of samples: A, dominant direction, and an 18-bin histogram (10° bins) for the rose plot. Taking samples as input lets a region combine only its own. |

---

## Per region: `measures/tortuosity.py` and `measures/anisotropy.py`

Both scan the whole image once, then report each region from that one scan. Segments touching a
flaked patch are left out, as in the crack stats.

| Function | File, line | What it does |
|---|---|---|
| `scan_curvature` | `tortuosity.py`, 18 | `compute_edge_curvature` on every segment, once per image. |
| `curvature_in_region` | `tortuosity.py`, 24 | Keeps the kept segments whose middle pixel is in the region (page 6). |
| `measure_tortuosity` | `tortuosity.py`, 33 | The region's columns: mean and median tortuosity over segments long enough to trust, mean and maximum curvature in 1/µm, and how many segments each is based on. |
| `scan_orientations` | `anisotropy.py`, 21 | Direction samples along every kept segment, once per image. |
| `anisotropy_in_region` | `anisotropy.py`, 28 | Combines the samples lying inside the region. Samples are local, so each goes by its own position, not its segment's middle. |
| `measure_anisotropy` | `anisotropy.py`, 35 | The region's columns: anisotropy index, dominant bearing, number of samples. |

Curvature is measured in 1/px and divided by µm per pixel to give 1/µm.

---

## Worth knowing

- **Flaked segments are left out without rebuilding the graph**, the same way as in the crack
  stats. Before 2026-11-13, the per-image tool rebuilt the graph instead, which could merge two
  segments into one, so its tortuosity and anisotropy can differ slightly from older runs.
- **A small region has few segments.** Each row says how many segments or samples its numbers
  rest on (`tortuosity_n_segments`, `anisotropy_n_samples`); treat values from a handful with
  care.
- **Tests**:
  - `tests/test_curvature.py` (7 tests): straight arms, a known circular arc, a sharp kink,
    short segments, and degenerate segments.
  - `tests/test_anisotropy.py` (7 tests): all-parallel, random, orthogonal grid (the blind
    spot), and histogram consistency.
