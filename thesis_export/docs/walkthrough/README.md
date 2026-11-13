# Code walkthrough

A file-by-file tour of `thesis_export/`, in the order data flows through it, with line
references. In VS Code, press **Ctrl+Shift+V** on a page to read it formatted.

Line numbers match the code as of 2026-11-13. If they drift, search for the function name.

## The big picture

```
your settings (settings.py)                µm per pixel, regions, measurements, figures
  │
micrograph (.jpg)
  │
  ├─ ENGINE, once per image (engine.py)
  │   ├─ 1. load            io_utils.py         grey + colour pixel grids
  │   ├─ 2. binarize        binarize.py         crack / not-crack mask
  │   ├─ 3. skeletonize     skeleton.py         1-pixel centre lines, junk branches removed
  │   │     └─ flaking      flaking.py          flaked patches; flag segments touching them
  │   └─ 4. graph           graph.py            network of junctions + segments
  │
  ├─ REGIONS (regions.py)                       whole image, centre, or chosen grid cells
  │
  ├─ MEASUREMENTS, per region (measures/)
  │   ├─ crack_stats.py     area, width, segment length, connectivity (whole image only)
  │   ├─ tortuosity.py      how bent the segments are   (curvature.py)
  │   ├─ anisotropy.py      rose plot of crack directions   (anisotropy.py)
  │   └─ segments.py        optional: one row per segment
  │
  └─ OUTPUT (analysis.py, export.py, figures.py)
        results.xlsx: one row per image and region, plus the settings used
        figures: overlay with regions, per-region rose plots, colour map over the grid
```

Whole-image crack stats are the thesis's main numbers.

## Reading order

| # | Page | Files |
|---|---|---|
| 1 | [Loading and binarizing](01_load_and_binarize.md) | `io_utils.py`, `binarize.py` |
| 2 | [Skeletonizing](02_skeleton.md) | `skeleton.py` |
| 3 | [Flaking exclusion](03_flaking.md) | `flaking.py` |
| 4 | [The crack network](04_graph.md) | `graph.py` |
| 5 | [Settings and the engine](05_settings_and_engine.md) | `settings.py`, `engine.py` |
| 6 | [Regions](06_regions.md) | `regions.py` |
| 7 | [Crack stats](07_crack_stats.md) | `measures/crack_stats.py` |
| 8 | [Curvature, tortuosity and anisotropy](08_curvature_anisotropy.md) | `curvature.py`, `anisotropy.py`, `_chord_scan.py`, `measures/` |
| 9 | [One run, start to finish](09_analysis_and_outputs.md) | `analysis.py`, `measures/segments.py`, `export.py`, `figures.py` |
| 10 | [Command line and GUI](10_command_line_and_gui.md) | `src/analyze.py`, `app.py`, `scripts/batch_stats/` |
| 11 | [Validation and tests](11_validation_and_tests.md) | `synthetic*.py`, `validation_*.py`, `scripts/validation/`, `tests/` |

Pages 1–7: the crack stats. Page 8: shape measurements. Pages 9–11: running and checking.

## Conventions

- **Coordinates are (row, column)**, row 0 at the top. Plotting code flips to (x, y).
- **Bearings**: degrees, 0° = right, 90° = up. Axial bearings treat 10° and 190° as the same.
- **`path_index`**: skan's number for one segment. Most per-segment results are keyed by it.
- **Degree**: segments meeting at a point. 1 = loose end, 3 = three-way junction, 4+ = crossing.
- **`...Result` classes**: plain containers (`@dataclass`) for one step's output.
- **Evidence labels** (a heuristic, assigned by judgement): `[measured]` read from the image;
  `[interpreted]` depends on a modelling choice; `[speculated]` a hypothesis; `[cited]` from the
  literature.
- **🔴 / 🟡 / 🟢** (a heuristic): how well a setting is justified (`CALIBRATION.md`).

Terms: [`GLOSSARY.md`](../../GLOSSARY.md).

Figures in `img/` (pages 1–2) come from `python3 -m scripts.docs.make_walkthrough_figures`.
`real_pruned_branches.png` needs real micrographs in `data/raw`.
