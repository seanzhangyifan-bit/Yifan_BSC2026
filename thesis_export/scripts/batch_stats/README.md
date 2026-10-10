# Batch crack-stats export

**Purpose**: turn a folder of micrographs into one numeric spreadsheet — crack area, width,
segment length, connectivity — for the thesis's cross-condition tables (SSC vs LSC, four
Rakelspalt gap settings) and for the sibling `image_visualization` repo, which reads these
spreadsheets and never hand-edits them. This is stage 1-3 only (binarize → skeletonize → graph
extraction) — no junctions, no ordering, no timing claims. See
`../../docs/batch_stats/crack_stats_schema.md` for the full column reference.

**Two independent methodologies, not one script with a version flag** — both remain runnable,
neither replaces the other:

- **`export_crack_stats.py`** ("v1"/"v2" in the docs — same script, different scope/flags): the
  original, exercised over the full 39-image dataset. Excludes flaked/delaminated regions with a
  two-pass skeletonize (scout for reference width → grow the excluded region back to its true
  boundary → re-skeletonize the corrected mask). Run: `python3 -m scripts.batch_stats.export_crack_stats [--out outputs/crack_stats.xlsx]`.
- **`export_crack_stats_v3.py`** + **`export_crack_stats_v3_batch_bcd.py`**: an alternate,
  single-pass methodology — skip the second skeletonize, and instead of a distance-buffer cut,
  omit any edge with a pixel physically inside the excluded region. ~2x faster per image.
  **Validation status**: cross-checked against v1/v2 on the 13 images both cover — batch images
  with zero flaking match to 0.0% on every column; images that do have flaking show differences
  of 2-4.5% mean (up to 30-37% on the sparsest/most-flaked images), and those differences track
  the disclosed methodology change exactly, nowhere else (`../../docs/batch_stats/crack_stats_schema.md`
  §10 has the full comparison). `add_definitions_sheet.py` appends a plain-language definitions sheet
  to a v3 workbook.

**Not run against the full dataset**: v3 has only been run on a 19-image scoped batch so far, not
the full 39-image set v1 covers.
