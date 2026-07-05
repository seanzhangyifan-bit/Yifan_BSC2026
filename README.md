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
| 4 | Annulus angle measurement, T-vs-Y classification | Not built |
| 5 | Precedence graph → transitive closure → DAG/cycle check | Not built |
| 6 | Width `w` (Dilworth/König), junction census, generation counts | Not built |

**What you get right now:** a skeleton, a planar graph, and junction
locations classified only by node degree (endpoint = degree 1, junction =
degree ≥ 3). There is **no T-vs-Y distinction and no partial order yet** —
that needs stage 4's annulus angle measurement, which hasn't been built.
Don't mistake the current overlay/report for the thesis's actual finding;
it's a topology checkpoint.

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

### Output

- Console report: threshold + foreground fraction (stage 1), skeleton pixel
  counts pre/post-prune + spur/fragment counts (stage 2), node/edge counts
  broken down by degree (stage 3). Every number is labeled `[measured]` or
  `[placeholder]`/`[interpreted]` per the evidence-level discipline in
  CLAUDE.md.
- `outputs/{image_stem}_corner_overlay.png` (or `_full_overlay.png` with
  `--full-image`): the analyzed region with the skeleton drawn in green,
  junction nodes (degree ≥ 3) in red, endpoints (degree 1) in orange.

## Verifying it works

Two checks, in order — no full-image run yet (see above):

1. **Synthetic correctness check** (known ground truth):
   ```
   python3 -m pytest tests/test_synthetic.py -v
   ```
   Renders a minimal image with exactly one T-junction and asserts the
   pipeline recovers exactly 1 junction (degree 3), 3 endpoints, and 3
   edges — validates the full stage 1-3 chain against a case with a known
   right answer, not just "runs without crashing."

2. **Real-image corner crop, visual check**:
   ```
   python3 -m src.analyze_image data/raw/T5/T5-M_H95_v1_mm000001.jpg
   ```
   then open `outputs/T5-M_H95_v1_mm000001_corner_overlay.png` and confirm
   by eye that the green skeleton tracks the real crack lines and red/orange
   markers sit at actual junctions/tips.

## Repo layout

```
src/
  crackgraph/
    io_utils.py    # image loading
    region.py      # default top-left corner crop selection
    binarize.py    # stage 1
    skeleton.py    # stage 2 (skeletonize + iterative spur pruning via skan)
    graph.py       # stage 3 (skan graph extraction, degree-based classification)
    overlay.py     # overlay PNG rendering
    synthetic.py   # synthetic T-junction test-image generator
  analyze_image.py # CLI entry point
tests/
  test_synthetic.py
```
