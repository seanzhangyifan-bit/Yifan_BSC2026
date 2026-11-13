# Batch crack-stats spreadsheets

Helpers for the thesis's crack-stats spreadsheets. The analysis itself lives in `src/` and runs
from the GUI or `python3 -m src.analyze` (see the root README); these scripts only add what the
thesis tables needed on top. Column reference: `../../docs/batch_stats/crack_stats_schema.md`.

- **`export_crack_stats_batch_bcd.py`**: crack stats on the whole image for three fixed thesis
  batches (B, C, D; 19 images), with runtime columns and a `batch` column. Run
  `python3 -m scripts.batch_stats.export_crack_stats_batch_bcd --data-dir <your image folder>`.
- **`add_definitions_sheet.py`**: appends a plain-language definitions sheet to a finished
  workbook.
