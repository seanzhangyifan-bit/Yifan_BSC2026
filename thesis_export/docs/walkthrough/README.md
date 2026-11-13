# Code walkthrough

A plain-language tour of every part of `thesis_export/`, in the order the data flows through it.
Each page explains what a file is for, then goes through it function by function, pointing at
the lines that matter.

To read it formatted in VS Code, open a page and press **Ctrl+Shift+V**.

Line numbers match the code after the 2026-11-13 merge of the three analysis tools into one (see
`CHANGELOG.md`). If a file changes later, function names stay the easiest way to find your place.

## The big picture

The project turns a micrograph of a cracked catalyst layer into numbers that let crack patterns
be compared across conditions. One run, from the GUI or the command line, goes like this:

```
your settings (settings.py)                µm per pixel, regions, measurements, figures
  │
micrograph (.jpg)
  │
  ├─ ENGINE, once per image (engine.py)
  │   ├─ 1. load            io_utils.py         grey + colour pixel grids
  │   ├─ 2. binarize        binarize.py         crack / not-crack mask
  │   ├─ 3. skeletonize     skeleton.py         1-pixel centre lines, junk branches removed
  │   │     └─ flaking      flaking.py          find flaked-off patches, flag segments touching them
  │   └─ 4. graph           graph.py            network of junctions + segments
  │
  ├─ REGIONS (regions.py)                       whole image, centre, or chosen grid cells
  │
  ├─ MEASUREMENTS, per region (measures/)
  │   ├─ crack_stats.py     area, width, segment length, connectivity (whole image only)
  │   ├─ tortuosity.py      how bent the segments are    (curvature.py)
  │   ├─ anisotropy.py      whether cracks share a direction  (anisotropy.py)
  │   └─ segments.py        optional: one row per segment
  │
  └─ OUTPUT (analysis.py, export.py, figures.py)
        results.xlsx: one row per image and region, plus the settings used
        figures: overlay with regions, per-region rose plots, colour map over the grid
```

The crack stats on the whole image are the thesis's main numbers.

## Reading order

| # | Page | Files | Why read it |
|---|---|---|---|
| 1 | [Loading and binarizing](01_load_and_binarize.md) | `io_utils.py`, `binarize.py` | Where every analysis starts |
| 2 | [Skeletonizing](02_skeleton.md) | `skeleton.py` | Turns thick cracks into measurable lines |
| 3 | [Flaking exclusion](03_flaking.md) | `flaking.py` | Keeps missing material out of the stats |
| 4 | [The crack network](04_graph.md) | `graph.py` | Junctions, segments, and skan's vocabulary |
| 5 | [Settings and the engine](05_settings_and_engine.md) | `settings.py`, `engine.py` | What you can change, and the one pass every measurement shares |
| 6 | [Regions](06_regions.md) | `regions.py` | Whole image, centre or grid cells, and how a region cuts the numbers |
| 7 | [Crack stats](07_crack_stats.md) | `measures/crack_stats.py` | Every crack-stats number |
| 8 | [Curvature, tortuosity and anisotropy](08_curvature_anisotropy.md) | `curvature.py`, `anisotropy.py`, `_chord_scan.py`, `measures/` | Shape of the network |
| 9 | [One run, start to finish](09_analysis_and_outputs.md) | `analysis.py`, `measures/segments.py`, `export.py`, `figures.py` | How it all runs together, and what it writes |
| 10 | [Command line and GUI](10_command_line_and_gui.md) | `src/analyze.py`, `app.py`, `scripts/batch_stats/` | How to run it |
| 11 | [Validation and tests](11_validation_and_tests.md) | `synthetic*.py`, `validation_*.py`, `scripts/validation/`, `tests/` | How we know it works |

Pages 1–7 cover the crack stats and take a few hours. Page 8 covers the shape measurements.
Pages 9–11 show how a run is put together and checked.

## Ideas that come up everywhere

- **Pixel coordinates are (row, column)**, not (x, y). Row 0 is the top of the image. Plotting
  code flips them to (x, y) right before drawing.
- **Bearings** are directions in degrees: 0° points right (east), 90° points up (north), and
  they run from −180° to 180°. "Axial" bearings ignore which way along a line you face, so 10°
  and 190° count as the same.
- **`path_index`** is skan's number for one skeleton segment, the stretch between two junctions
  or endpoints. Almost every per-segment result is keyed by it.
- **Degree** is how many segments meet at a point: 1 = a loose end, 3 = a three-way junction,
  4 or more = a crossing.
- **`...Result` classes** are plain containers (Python `@dataclass`) that bundle everything one
  step produces. Each step takes the previous step's result and returns its own.
- **Evidence labels** in comments say how much to trust a number:
  - `[measured]`: read directly from the image.
  - `[interpreted]`: depends on a modelling choice.
  - `[speculated]`: a hypothesis.
  - `[cited]`: from the literature.
- **🔴 / 🟡 / 🟢** mark how well a tunable setting is justified. See `CALIBRATION.md`.

Terms are defined in [`GLOSSARY.md`](../../GLOSSARY.md). Known problems are listed in
[`docs/reviews/2026-11-11-full-code-review.md`](../reviews/2026-11-11-full-code-review.md). This
walkthrough mentions the relevant review findings where they apply.

The figures in `img/` (used in pages 1 and 2) come from
`scripts/docs/make_walkthrough_figures.py`. Most run the real library call on a small
made-up shape; `real_pruned_branches.png` runs the pipeline on real micrographs from `data/raw`.
To redraw them, run `python3 -m scripts.docs.make_walkthrough_figures`.
