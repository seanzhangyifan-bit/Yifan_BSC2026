# Thesis submission export

A standalone, runnable copy of the full crack-pattern analysis codebase from the parent
`crack-project` repository — the software artifact submitted alongside the written BSc thesis
(KIT, Thin Film Technology group; PEMFC catalyst-layer ink formulation and coating). Doesn't
depend on the rest of that repository; everything needed to run every deliverable below is in
this folder.

**Start here for the science**: [`METHODOLOGY.md`](METHODOLOGY.md) explains *why* the analysis targets a
partial order of crack growth rather than a full chronology — read that before the deliverables
below make full sense. [`GLOSSARY.md`](GLOSSARY.md) has one-line term definitions;
[`CALIBRATION.md`](CALIBRATION.md) has the calibration status of every tunable constant.

## Setup

You need Python 3 and pip. From inside this folder:

```
python3 -m venv venv
source venv/bin/activate   # on Windows: venv\Scripts\activate
pip install -r requirements.txt
```

The virtual environment step is optional but keeps this project's dependencies separate from
anything else on your machine. That one `pip install` line installs everything you need: the
analysis libraries, `pytest` (for running `tests/`), and `streamlit` (for the GUI) — there's no
separate install step for any of them.

**If `streamlit run app.py` says `streamlit: command not found`**: the package installed, but
the `streamlit` command isn't on your shell's `$PATH` (common with certain pip setups). Run it
through Python directly instead — this always works once the install above succeeded:

```
python3 -m streamlit run app.py
```

## A note on authorship

This project's scientific direction, methodology design, and every interpretive decision are the
author's own (BSc thesis work, KIT Thin Film Technology group) — the choice to reconstruct a
partial order rather than a chronology, the annulus/corner-cross-check measurement design, which
constants get swept vs. asserted, and how every result in this repo is read and reported. The
code implementation was written with AI assistance (Claude, Anthropic) under the author's
direction and review, not autonomously.

## Repo layout

- **`src/`** — the library: the analysis engine itself (`src/crackgraph/`'s
  binarize → skeletonize → graph → junctions → precedence chain), plus
  `src/analyze_image.py` as the one CLI entry point that wires those pieces together for a
  single image. Meant to be imported, not run standalone except via that entry point.
- **`scripts/`** — standalone tools built on top of `src/`, one per job: `batch_stats/`
  (the spreadsheet export), `spatial_overview/` (the quadrant-comparison figure),
  `validation/` (synthetic ground-truth galleries and calibration sweeps),
  `experimental/` (throwaway exploratory code). Each is run directly (e.g.
  `python3 -m scripts.batch_stats.export_crack_stats`), not imported elsewhere.
- **`tests/`** — pytest correctness checks for `src/` (known-ground-truth synthetic
  cases), run via `pytest tests/`. Never part of normal use — only run to confirm nothing
  broke.
- **`__pycache__/`** — not source code. Python auto-generates this the first time it
  imports a file, to cache compiled bytecode for faster imports; it reappears on its own
  and is safe to delete anytime. Already excluded from version control.

## The five deliverables

This project isn't one pipeline — it's five semi-independent pieces of work at different
validation levels. Each has its own folder-level README with full detail; this table is the map.

| # | Deliverable | What it does | Validation level | Where |
|---|---|---|---|---|
| 1 | **Per-image pipeline** | Junction classification (T/Y), precedence-graph assembly | Synthetic ground-truth pytest suite + sweep-justified window constants + corner-cross-check agreement + real-image visual review | `src/`, run via `python3 -m src.analyze_image <image_path>` |
| 2 | **Batch crack-stats export** | Numeric spreadsheets (crack density, width, connectivity) across many images/conditions | Two independent methodologies (v1/v2, v3) cross-validated against each other on real images; batch-level sanity-band checks | `scripts/batch_stats/` |
| 3 | **Spatial overview & report** | First-look spatial-variation figures + one master HTML report across all analyzed images | None formal — deliberately a first look, not a citable result | `scripts/spatial_overview/` |
| 4 | **Methodology validation & QA** | Synthetic ground-truth galleries + calibration sweeps that justify the per-image pipeline's tunable constants | This *is* the validation evidence for #1 | `scripts/validation/` |
| 5 | **Exploratory / future work** | In-situ video-tracking hypothesis + a throwaway tracing PoC | Explicitly unvalidated, not integrated | `scripts/experimental/` |

## Running the per-image pipeline

```
python3 -m src.analyze_image path/to/image.jpg
```

Binarizes, skeletonizes, classifies every junction, cross-checks against an independent
background-corner method, and assembles a precedence graph — console report plus overlay PNGs
under `outputs/<source-subfolder>/`. See `METHODOLOGY.md`'s "Pipeline shape" and README-equivalent
sections above for the full stage-by-stage description and every CLI flag.

## GUI (optional, easiest way to try this)

No command-line flags to learn: upload one or more images, choose what to run, click go.

```
python3 -m streamlit run app.py
```

(See [Setup](#setup) above if the bare `streamlit run app.py` command isn't found.) Opens
locally at `http://localhost:8501` — runs entirely on your own machine, nothing is uploaded
anywhere.

Upload one or more micrographs, then check off what you want run on them: crack stats (density,
width, connectivity), curvature & tortuosity, anisotropy, junction classification
(T/Y), corner cross-check, precedence graph, and spatial overview (a quadrant-comparison figure)
— any combination. Corner cross-check and the precedence graph both need junction classification
turned on, so the app disables them until you check that box first. A progress bar tracks each
image through whichever stages you selected, with a rough elapsed-time/time-remaining estimate.

This is a thin front-end onto deliverables #1, #2, and #3 below — same underlying scripts as the
CLI, same validation status, not a separate method. Deliverables #4 (validation gallery) and #5
(experimental) are intentionally **not** in the GUI: #4 is evidence *about* the pipeline's
correctness, not something you'd run against your own image, and #5 is explicitly unvalidated
future work, not something to present next to real results. Deliverable #2's µm/mm² columns
assume this project's own microscope calibration, which almost certainly doesn't apply to a
different image source — the app flags this next to those columns rather than presenting them as
universally correct. Deliverable #3's figure carries no formal validation either, same as its row
in the table below — the app's checkbox says so directly.

## What's not included

- **`data/raw/`** — the private micrograph collection this pipeline was developed and run
  against. Not bundled (large, and not the parent repo's own to redistribute). Point any script
  at your own images instead.
- **`crack_stats_export/`** — a separate, smaller export in the parent repo, built specifically
  for the sibling `image_visualization` project to consume `crack_stats.xlsx`. Different purpose
  from this folder (a thesis-submission archive of the whole project); not duplicated here.

## `examples/`

Already-produced outputs, so you can see real results without running anything yourself: three
spreadsheets from real runs against the private micrograph collection (proof this pipeline was
actually exercised on real data, not just unit-tested — these specifically can't be regenerated
from this export alone, since that needs the private `data/raw/` source images), plus
`examples/validation_gallery.html` — a self-contained copy of the synthetic-pattern validation
gallery (14 ground-truth cases across all 5 measurement methods, see deliverable #4 below). Open
it directly in a browser, no server needed. See `examples/README.md` for exactly what's here and
how each file was produced.

## Tests

```
python3 -m pytest tests/ -v
```

Full suite: synthetic-ground-truth correctness checks (known junction angles, known crack
widths) plus regression tests for every fix described in the docs above. All tests
pass in a fresh venv built from this folder's own `requirements.txt` alone — verified as part of
producing this export, not assumed.
