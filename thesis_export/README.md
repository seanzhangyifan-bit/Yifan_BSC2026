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

```
pip install -r requirements.txt
```

## A note on authorship

This project's scientific direction, methodology design, and every interpretive decision are the
author's own (BSc thesis work, KIT Thin Film Technology group) — the choice to reconstruct a
partial order rather than a chronology, the annulus/corner-cross-check measurement design, which
constants get swept vs. asserted, and how every result in this repo is read and reported. The
code implementation was written with AI assistance (Claude, Anthropic) under the author's
direction and review, not autonomously.

## The five deliverables

This project isn't one pipeline — it's five semi-independent pieces of work at different
validation levels. Each has its own folder-level README with full detail; this table is the map.

| # | Deliverable | What it does | Validation level | Where |
|---|---|---|---|---|
| 1 | **Core per-image pipeline** | Junction classification (T/Y), precedence-graph assembly — the thesis's actual scientific contribution | Synthetic ground-truth pytest suite + sweep-justified window constants + corner-cross-check agreement + real-image visual review | `src/`, run via `python3 -m src.analyze_image <image_path>` |
| 2 | **Batch crack-stats export** | Numeric spreadsheets (crack density, width, connectivity) across many images/conditions | Two independent methodologies (v1/v2, v3) cross-validated against each other on real images; batch-level sanity-band checks | `scripts/batch_stats/` |
| 3 | **Spatial overview & report** | First-look spatial-variation figures + one master HTML report across all analyzed images | None formal — deliberately a first look, not a citable result | `scripts/spatial_overview/` |
| 4 | **Methodology validation & QA** | Synthetic ground-truth galleries + calibration sweeps that justify the core pipeline's tunable constants | This *is* the validation evidence for #1 | `scripts/validation/` |
| 5 | **Exploratory / future work** | In-situ video-tracking hypothesis + a throwaway tracing PoC | Explicitly unvalidated, not integrated | `scripts/experimental/` |

## Running the core pipeline

```
python3 -m src.analyze_image path/to/image.jpg
```

Binarizes, skeletonizes, classifies every junction, cross-checks against an independent
background-corner method, and assembles a precedence graph — console report plus overlay PNGs
under `outputs/<source-subfolder>/`. See `METHODOLOGY.md`'s "Pipeline shape" and README-equivalent
sections above for the full stage-by-stage description and every CLI flag.

## GUI (optional, easiest way to try this)

No command-line flags to learn: upload an image, click run, see the result in your browser.

```
streamlit run app.py
```

Opens locally at `http://localhost:8501` — runs entirely on your own machine, nothing is
uploaded anywhere. Two modes:

- **Single image**: upload one micrograph, see the overlay and console report rendered inline.
- **Batch folder**: upload several images, get back a results table (crack density, width,
  connectivity) with a spreadsheet download.

This is a thin front-end onto deliverables #1 and #2 below — same underlying pipeline as the CLI,
same validation status, not a separate method. Deliverable #2's µm/mm² columns assume this
project's own microscope calibration, which almost certainly doesn't apply to a different image
source — the app flags this next to those columns rather than presenting them as universally
correct.

## What's not included

- **`data/raw/`** — the private micrograph collection this pipeline was developed and run
  against. Not bundled (large, and not the parent repo's own to redistribute). Point any script
  at your own images instead.
- **`crack_stats_export/`** — a separate, smaller export in the parent repo, built specifically
  for the sibling `image_visualization` project to consume `crack_stats.xlsx`. Different purpose
  from this folder (a thesis-submission archive of the whole project); not duplicated here.

## `examples/`

Already-produced outputs from real runs — proof this pipeline was actually exercised on real
data, not just unit-tested. These can't be regenerated from this export alone (they need the
private `data/raw/` source images) — see `examples/README.md` for exactly what's here and how it
was produced.

## Tests

```
python3 -m pytest tests/ -v
```

Full suite: synthetic-ground-truth correctness checks (known junction angles, known kink corners,
known crack widths) plus regression tests for every fix described in the docs above. All tests
pass in a fresh venv built from this folder's own `requirements.txt` alone — verified as part of
producing this export, not assumed.
