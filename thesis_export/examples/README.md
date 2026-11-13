# Examples

| File | Made by | Contents |
|---|---|---|
| `crack_stats_batch_bcd.xlsx` | `scripts/batch_stats/export_crack_stats_batch_bcd.py` | Thesis batches B, C, D (19 images), with a `definitions` sheet. Made before the 2026-11-11 pruning changes; `n_corner_artifacts_pruned` is now `n_host_stubs_pruned`, and region columns are missing. Re-run for current numbers. |
| `validation_gallery.html` | `scripts/validation/validation_gallery.py` | 5 synthetic cases (curvature, anisotropy), expected vs measured. |

- The spreadsheet needs the private `data/raw/` images, so it can't be regenerated here. Its
  numbers are real output.
- The gallery needs no private data: regenerate with
  `python3 -m scripts.validation.validation_gallery`. This copy has its images inlined so it works
  as a single file.
- Column meanings: `../docs/batch_stats/crack_stats_schema.md`.
