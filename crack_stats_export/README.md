# crack_stats export

A small, standalone piece of a larger BSc-thesis project on fuel-cell catalyst-layer coatings. This
folder measures how much a coating has cracked, from photos of the coating under a microscope, and
writes the results to one spreadsheet, `crack_stats.xlsx`.

**Not included here**: a separate, unexported part of the parent project tries to figure out *which
crack formed before which* from how cracks meet each other. That's a different, more speculative
analysis — this folder only measures things you can read straight off the picture (how much area is
cracked, how wide the cracks are, how connected the network is), nothing about timing or order.

## Folder layout

| Path | What it is |
|---|---|
| `export_crack_stats.py` | Run this to (re)generate `crack_stats.xlsx` from a folder of photos. |
| `crackgraph/` | The measurement code itself, in 3 small steps — see "How it works" below. |
| `docs/crack_stats_schema.md` | What every column in the spreadsheet means, exactly. |
| `crack_stats.xlsx` | The real, current output — 39 rows, one per photo. |
| `examples/schematic_and_examples.html` | Open this in a browser — see "The demo page" below. |
| `requirements.txt` | The Python packages you need, and the exact versions this was tested with. |

## Quickstart

```
pip install -r requirements.txt
python3 export_crack_stats.py --out crack_stats.xlsx
```

By default this looks for a `data/raw/` folder next to the script, with filenames like
`sample_v1_mm000001.jpg` — this project's own naming convention (details in
`docs/crack_stats_schema.md` §2–3). That private photo collection isn't included in this export —
the bundled `crack_stats.xlsx` is the real output already produced from it.

**To point this at your own photos**, three flags override everything relevant, and none of them
require touching the code:

```
python3 export_crack_stats.py \
  --input-dir my_photos \
  --pattern "**/*.jpg" \
  --um-per-px 0.45 \
  --out my_results.xlsx
```

- `--input-dir` / `--pattern` — where to look and which files count.
- `--um-per-px` — how many real-world micrometers one pixel covers, for the physical-unit columns
  (area in mm², width in µm). There's no way for the script to guess this from your camera/microscope
  — you have to know it and supply it. Leave it out and it'll use this project's own value, which is
  almost certainly wrong for a different setup (it won't error, it'll just silently give you the
  wrong numbers — see `docs/crack_stats_schema.md` §6 for how this project's own value was measured).

## How it works, in plain terms

No familiarity with the underlying image-processing libraries is assumed — here's what actually
happens to a photo, step by step.

**1. Deciding which pixels are "crack".** A microscope photo of a cracked coating is just bright
crack lines on a darker background. To measure anything, the computer first needs to label every
single pixel "crack" or "not crack." It does this with a well-known technique called Otsu
thresholding (`scikit-image` is the library that runs it): look at how bright every pixel in the
photo is, and automatically pick the brightness cutoff that best splits the picture into two clean
groups. No manual "is this bright enough to count" tuning needed.

**2. Shrinking each crack down to a single line.** In the photo, a crack is a thick smear of pixels,
not a thin line — but questions like "how long is this crack" or "how many times does it branch" are
much easier to answer from a thin line than a blob. So the code shrinks ("skeletonizes") every crack
down to a path exactly one pixel wide, using a standard thinning algorithm that peels pixels off the
edges a layer at a time, in a way that's mathematically guaranteed to never break a connection or
invent a new one.

**3. Turning that line drawing into numbers.** Once every crack is a thin line, the code treats the
whole picture like a road map: anywhere three or more lines meet becomes a "junction," any dead end
becomes an "endpoint," and each stretch of line between two of those becomes an "edge." A library
called `skan` walks the thinned image and produces exactly that list. From there, it's just counting:
how many disconnected pieces of crack network are there (`networkx` answers this), how long is the
average stretch between two junctions, and so on.

**Turning that into the spreadsheet.** Total cracked area ÷ total crack-network length gives an
average crack width. Total length ÷ number of edges gives an average distance between junctions. How
much of the total crack length belongs to one single connected piece tells you whether the coating's
cracks form one continuous web or lots of separate islands. The exact formula, unit, and confidence
level for every one of the 13 columns is in `docs/crack_stats_schema.md` — this README won't
re-explain each one.

## Worth knowing before trusting the numbers

- The pixel-pruning threshold in `crackgraph/skeleton.py` (`SPUR_PX_PLACEHOLDER = 15`) is flagged in
  the code as a genuine guess, not a settled value — it controls how aggressively tiny leftover
  specks get cleaned up before measuring.
- The built-in "does this crack-area percentage look plausible" sanity check (1–15%) doesn't hold up
  well outside the sample family it was tuned on — 23 of the current 39 rows fall outside it. Every
  row is still included; see `docs/crack_stats_schema.md` §7 for why.
- `avg_width_px` is a rough estimate (area ÷ length), not a precise measurement — see
  `docs/crack_stats_schema.md` §4 before treating it as exact.
- On wide or irregular cracks, the line-thinning step can occasionally trace both edges of the crack
  for a short stretch instead of settling on one clean centerline, leaving a tiny loop behind. This
  inflates the edge count and makes `avg_edge_length_px` read a bit lower than it should for affected
  photos — measured at 0–55% of edges depending on the photo, not tied to any one sample type. See
  `docs/crack_stats_schema.md` §4 for the numbers.

## The demo page

Open `examples/schematic_and_examples.html` in any browser (no install, no server — it's just a
static page with images next to it).

- **Schematic section**: two made-up test patterns with a known, exact right answer (a single
  straight line of known length; a simple T-shaped junction), run through the same code as above, so
  you can see the measured numbers land right next to what they *should* be. This is the actual proof
  that the method measures what it claims to — and you can regenerate it yourself with
  `cd examples && python3 generate_examples.py`, no private data needed.
- **Real examples**: the same code run on three real photos already in `crack_stats.xlsx` (barely
  any cracking, typical, and heavily cracked). These panels can't be regenerated from this export
  alone — `generate_examples.py` points at the original private photo collection by its exact
  location on the machine this was built on — but the images and numbers shown are the real,
  already-produced output, not a mockup.
