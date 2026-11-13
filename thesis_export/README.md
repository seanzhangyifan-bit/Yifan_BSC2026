# Crack-pattern analysis (thesis export)

The analysis code submitted with the BSc thesis (Zhang 2026, KIT Thin Film Technology group;
PEMFC catalyst-layer coating). Self-contained: everything needed to run it is in this folder.

- [`METHODOLOGY.md`](METHODOLOGY.md): what is measured and why. Read first.
- [`docs/walkthrough/`](docs/walkthrough/README.md): file-by-file tour of the code.
- [`docs/batch_stats/crack_stats_schema.md`](docs/batch_stats/crack_stats_schema.md): every column.
- [`CALIBRATION.md`](CALIBRATION.md): how well each tunable constant is justified.
- [`GLOSSARY.md`](GLOSSARY.md): term definitions.
- [`CHANGELOG.md`](CHANGELOG.md): every change, and whether it affects results.

## Setup

Python 3 and pip. From this folder:

```
python3 -m venv venv                 # optional
source venv/bin/activate             # Windows: venv\Scripts\activate
pip install -r requirements.txt      # analysis libraries, pytest, streamlit
```

## Running it

**GUI:**

```
python3 -m streamlit run app.py
```

Opens at `http://localhost:8501`; runs locally, nothing is uploaded. Upload micrographs, choose
settings, click **Run analysis**, download the workbook. (Use the `python3 -m` form if
`streamlit run app.py` says "command not found".)

**Command line**, same settings:

```
# Crack stats on the whole image, every image in a folder
python3 -m src.analyze ../data/raw/T5 --out-dir outputs/t5

# Left column of a 3x3 grid, with tortuosity, anisotropy and per-region figures
python3 -m src.analyze image.jpg --regions grid --grid 3x3 --cells 1,4,7 \
    --measure crack_stats tortuosity anisotropy --figures overlay panels map
```

`python3 -m src.analyze --help` lists every option.

## What it does

| Setting | Choices |
|---|---|
| Calibration | µm per pixel. Default 0.6098 (the thesis microscope); set your own for other images. |
| Regions | Whole image, centre, or chosen cells of any grid. The image is analysed once; regions select part of that result, so cells add up to the whole image. |
| Measurements | **Crack stats**: area, width, segment length, flaking, pruning, connectivity (whole image only). **Tortuosity and curvature**: how bent segments are. **Anisotropy**: rose plot of crack directions. **Per-segment table**: length, width, area. |
| Figures | Skeleton overlay with regions; rose plot and tortuosity histogram per region; colour map of one column over the grid. |

Each run writes `results.xlsx`: one row per image and region, the settings used, and, when they
apply, whole-image connectivity and the per-segment table.

Whole-image crack stats are the thesis's main numbers.

## Layout

- `src/crackgraph/`: the library. Engine (binarize → skeletonize → flaking → graph), regions,
  `measures/`, outputs.
- `src/analyze.py`: command line. `app.py`: GUI.
- `scripts/batch_stats/`: the thesis batch spreadsheet. `scripts/validation/`: synthetic
  galleries and calibration sweeps. `scripts/docs/`: walkthrough figures.
- `tests/`: pytest checks against synthetic cases with known answers.
- `examples/`: a real batch spreadsheet and the validation gallery (see `examples/README.md`).

## Not included

- `data/raw/`: the private micrographs. Use your own images.

## Tests

```
python3 -m pytest tests/
```

Run from this folder. All pass in a fresh venv from `requirements.txt`.

## Authorship

The scientific direction, method design and every interpretive decision are the author's. The
code was written with AI assistance (Claude, Anthropic) under the author's direction and review.
