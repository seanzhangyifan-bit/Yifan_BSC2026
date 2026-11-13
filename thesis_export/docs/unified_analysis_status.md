# Unified analysis: status

The crack-stats export, `analyze_image.py` and the spatial overview became one tool on
2026-11-13 (merged into master the same day). Details: `CHANGELOG.md`.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| Region measurement | Engine once per image; regions cut its result. | One threshold and flaking reference per image; cells add up to the whole. |
| Spur cut-off, dark-speck limit | Stored in µm (9.15 µm, 48.3 µm²). | Physically justified; exactly 15 px and 130 px at 0.6098 µm/px. |
| Connectivity | Whole image only. | Region borders split the network. |
| Segments in a region | Whole segment, placed by its middle pixel. | Not counted twice or cut short. |
| Pixels in a region | Only those inside. | Cells add up to the whole. |
| Anisotropy | Rose plot only, no index. | A single index reads an orthogonal grid as random. |
| Old entry points | Archived. | One way to run the analysis. |

## Open

- [ ] Which engine settings the GUI exposes. Candidates: spur cut-off, dark-speck limit,
  curvature and orientation windows, flaking constants.
- [ ] Re-run `export_crack_stats_batch_bcd.py` to refresh `examples/crack_stats_batch_bcd.xlsx`.
- [ ] Check the grid figures on a dense real image (only T5-M_H190_v1 so far).
