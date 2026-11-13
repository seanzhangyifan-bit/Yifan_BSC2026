# Thesis submission export

A standalone, runnable copy of the full crack-pattern analysis codebase from the parent
`crack-project` repository — the software artifact submitted alongside the written BSc thesis
(KIT, Thin Film Technology group; PEMFC catalyst-layer ink formulation and coating). Doesn't
depend on the rest of that repository; everything needed to run every deliverable below is in
this folder.

**Start here for the science**: [`METHODOLOGY.md`](METHODOLOGY.md) explains what the analysis measures and
why — read that before the deliverables below make full sense. [`GLOSSARY.md`](GLOSSARY.md) has one-line term definitions;
[`CALIBRATION.md`](CALIBRATION.md) has the calibration status of every tunable constant.
[`CHANGELOG.md`](CHANGELOG.md) lists every fix and change, and whether it affects reported results.
[`docs/walkthrough/`](docs/walkthrough/README.md) is a plain-language, file-by-file tour of the code.

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
author's own (BSc thesis work, KIT Thin Film Technology group) — which quantities to measure and
how, which constants get swept vs. asserted, and how every result in this repo is read and reported. The
code implementation was written with AI assistance (Claude, Anthropic) under the author's
direction and review, not autonomously.

## Repo layout

- **`src/`**: the analysis.
  - `src/crackgraph/`: the library. An engine that runs once per image (binarize → skeletonize
    → flaking exclusion → crack graph), regions (whole image, centre, grid cells), and the
    measurements made on each region (`measures/`: crack stats, tortuosity, anisotropy,
    per-segment table).
  - `src/analyze.py`: the command line.
- **`app.py`**: the browser GUI. It offers the same settings as the command line.
- **`scripts/`**: tools built on top of `src/`, one folder per job: `batch_stats/` (the thesis
  batch spreadsheet), `validation/` (synthetic ground-truth galleries and calibration sweeps),
  `experimental/` (throwaway exploratory code), `docs/` (the walkthrough figures).
- **`tests/`**: pytest checks of `src/` against synthetic cases with known answers. Run them to
  confirm nothing broke; they're not part of normal use.
- **`__pycache__/`**: not source code. Python creates it to cache compiled files; it's safe to
  delete, and version control ignores it.

## What it does

One tool, with settings you choose:

1. **Calibration**: µm per pixel. The default, 0.6098, is the thesis microscope.
2. **Regions**: the whole image, its centre, or chosen cells of a grid of any size. The image is
   analysed once; each region gets its own row of numbers from that one result, so cells are
   measured identically and add up to the whole image.
3. **Measurements** per region:
   - **Crack stats**: crack area, width, segment length, flaking, pruning counts, and
     connectivity (whole image only). On the whole image, these are the thesis's main numbers.
   - **Tortuosity and curvature**: how bent the crack segments are.
   - **Anisotropy**: whether the cracks share a preferred direction.
   - **Per-segment table** (optional): length, width and area of every segment.
4. **Figures**: the skeleton overlay with regions outlined, a rose plot and tortuosity histogram
   per region laid out like the grid, and a colour map of any column over the grid.

Each run writes one `results.xlsx`: a row per image and region, the settings used, and, when they
apply, whole-image connectivity and the per-segment table.

| Part | Validation | Where |
|---|---|---|
| The analysis | Synthetic ground-truth tests; the whole-image crack stats match the earlier exporter exactly; sweep-justified curvature window | `src/`, `app.py` |
| Validation and QA | This *is* the evidence for the analysis | `scripts/validation/` |
| Exploratory work | In-situ video-tracking idea and a throwaway tracing proof of concept. Not validated, not connected | `scripts/experimental/` |

## Running it

**GUI**, the easiest way:

```
python3 -m streamlit run app.py
```

It opens at `http://localhost:8501` and runs on your own computer; nothing is uploaded. (See
[Setup](#setup) if the bare `streamlit run app.py` isn't found.) Upload micrographs, choose the
settings above, and click **Run analysis**. You get the figures, the tables, and a download
button for the workbook.

**Command line**, the same settings as options:

```
# Crack stats on the whole image, for every image in a folder
python3 -m src.analyze ../data/raw/T5 --out-dir outputs/t5

# The left column of a 3x3 grid, with tortuosity, anisotropy and the per-region figures
python3 -m src.analyze image.jpg --regions grid --grid 3x3 --cells 1,4,7 \
    --measure crack_stats tortuosity anisotropy --figures overlay panels map
```

`python3 -m src.analyze --help` lists every option; `docs/walkthrough/10_command_line_and_gui.md`
explains them.

**About the µm columns**: they use the µm per pixel you set. The default fits the thesis
microscope only; for other images, set your own. The `_px` columns don't depend on it.

**About small regions**: a region's numbers rest on fewer segments. Each row says how many
segments or samples its tortuosity and anisotropy are based on. Connectivity is only reported for
the whole image, because cutting the network at a region border splits it.

## What's not included

- **`data/raw/`** — the private micrograph collection this pipeline was developed and run
  against. Not bundled (large, and not the parent repo's own to redistribute). Give the command
  line your own image files or folders, or upload them in the GUI.
- **`crack_stats_export/`** — a separate, smaller export in the parent repo, built specifically
  for the sibling `image_visualization` project to consume `crack_stats.xlsx`. Different purpose
  from this folder (a thesis-submission archive of the whole project); not duplicated here.

## `examples/`

Already-produced outputs, so you can see results without running anything: a spreadsheet from a
real run on thesis batches B, C and D (it needs the private `data/raw/` images, so it can't be
regenerated from this folder alone), and `validation_gallery.html`, the synthetic validation
gallery (5 ground-truth cases for curvature and anisotropy), which opens directly in a browser.
See `examples/README.md` for how each was produced.

## Tests

```
python3 -m pytest tests/ -v
```

Run from this folder. Synthetic ground-truth checks (known crack lengths, widths, curvature and
orientation), regression tests for fixed bugs, and a check that the whole-image crack stats still
match the earlier exporter's frozen output. All tests
pass in a fresh venv built from this folder's own `requirements.txt` alone — verified as part of
producing this export, not assumed.
