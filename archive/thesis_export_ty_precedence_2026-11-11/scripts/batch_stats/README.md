# Batch crack-stats export

**Purpose**: turn a folder of micrographs into one numeric spreadsheet — crack area, width,
segment length, connectivity — for the thesis's cross-condition tables (SSC vs LSC, four
Rakelspalt gap settings) and for the sibling `image_visualization` repo, which reads these
spreadsheets and never hand-edits them. This is stage 1-3 only (binarize → skeletonize → graph
extraction) — no junctions, no ordering, no timing claims. See
`../../docs/batch_stats/crack_stats_schema.md` for the full column reference.

**Flaked regions** are handled in a single pass: the mask is skeletonized once, and any edge
with a pixel inside a flaked/delaminated region is omitted from the stats and the connectivity
graph.

- **`export_crack_stats.py`**: every image file under `--data-dir` (any subfolder), one row each. It doesn't
  select by file name: put only the images you want in the folder, or use the GUI. Run:
  `python3 -m scripts.batch_stats.export_crack_stats --data-dir <your image folder> [--out outputs/crack_stats.xlsx] [--cache-dir DIR] [--scale-bars-checked]`.
  `--data-dir` defaults to `data/raw` inside this folder, which isn't bundled. Pass
  `--scale-bars-checked` only if you have looked at every image for a burned-in scale bar;
  otherwise the `scale_bar_check` column says `not checked`.
- **`export_crack_stats_batch_bcd.py`**: the same export on three fixed thesis batches (B, C, D;
  19 images), with a `batch` column. Takes the same `--data-dir` and `--scale-bars-checked`.
- **`add_definitions_sheet.py`**: appends a plain-language definitions sheet to a finished
  workbook.
