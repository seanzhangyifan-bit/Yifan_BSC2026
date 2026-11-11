# Code walkthrough

A plain-language tour of every part of `thesis_export/`, in the order the data flows through it.
Each page explains what a file is for, then goes through it function by function, pointing at
the lines that matter.

To read it formatted in VS Code, open a page and press **Ctrl+Shift+V**.

Line numbers match the code after the second 2026-11-11 bug-fix pass (see `CHANGELOG.md`). If a
file changes later, function names stay the easiest way to find your place.

## The big picture

The project answers two questions about a micrograph of a cracked catalyst layer:

1. **How much cracking is there?** Crack area, width, segment length and connectivity. These are
   the *crack stats*, exported to spreadsheets.
2. **In what order did the cracks form?** Where one crack stops against another (a T-junction),
   the stopped crack is younger. Collecting those local facts gives a *partial order*: which
   cracks came before which, where the geometry can tell.

Both start with the same four steps:

```
micrograph (.jpg)
  │
  ├─ 1. load            io_utils.py         grey + colour pixel grids
  ├─ 2. binarize        binarize.py         crack / not-crack mask
  ├─ 3. skeletonize     skeleton.py         1-pixel centre lines, junk branches removed
  │     └─ flaking      flaking.py          find flaked-off patches, remove, skeletonize again
  ├─ 4. graph           graph.py            network of junctions + segments
  │
  ├──► crack stats      export_crack_stats.py          area, width, length, connectivity → .xlsx
  │
  └──► per-image analysis (analyze_image.py)
        ├─ edge_metrics.py   length, width and area per segment
        ├─ curvature.py      how bent each segment is
        ├─ anisotropy.py     whether cracks share a direction
        ├─ junctions.py      T / Y / ambiguous at each 3-way junction
        ├─ corners.py        independent second opinion on each junction
        └─ precedence.py     "which crack came first" graph
```

## Reading order

| # | Page | Files | Why read it |
|---|---|---|---|
| 1 | [Loading and binarizing](01_load_and_binarize.md) | `io_utils.py`, `binarize.py` | Where every analysis starts |
| 2 | [Skeletonizing](02_skeleton.md) | `skeleton.py` | Turns thick cracks into measurable lines |
| 3 | [Flaking exclusion](03_flaking.md) | `flaking.py` | Keeps missing material out of the stats |
| 4 | [The crack network](04_graph.md) | `graph.py` | Junctions, segments, and skan's vocabulary |
| 5 | [Crack-stats export](05_crack_stats_export.md) | `scripts/batch_stats/` | Every spreadsheet number |
| 6 | [Per-segment metrics](06_edge_metrics.md) | `edge_metrics.py` | Width and area per segment |
| 7 | [Junction classification](07_junctions.md) | `junctions.py` | T vs Y, the heart of the ordering |
| 8 | [Corner cross-check](08_corners.md) | `corners.py` | A second, independent angle measurement |
| 9 | [Precedence graph](09_precedence.md) | `precedence.py` | The partial order itself |
| 10 | [Curvature and anisotropy](10_curvature_anisotropy.md) | `curvature.py`, `anisotropy.py`, `_chord_scan.py` | Shape of the network |
| 11 | [The per-image command](11_analyze_image.md) | `analyze_image.py` | How it all runs together |
| 12 | [Outputs and reports](12_outputs.md) | `overlay.py`, `xlsx_report.py`, `cache_io.py`, plots, HTML, tiling | Pictures, spreadsheets, caches |
| 13 | [The GUI](13_gui.md) | `app.py` | The point-and-click front end |
| 14 | [Validation and tests](14_validation_and_tests.md) | `synthetic*.py`, `validation_*.py`, `scripts/validation/`, `tests/` | How we know it works |

Pages 1–5 cover the crack-stats path and take a few hours. Pages 6–11 cover the ordering
analysis. Pages 12–14 are supporting material you can skim.

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
