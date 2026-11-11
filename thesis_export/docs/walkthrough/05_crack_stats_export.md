# 5. Crack-stats export

**Folder**: `scripts/batch_stats/`
- `export_crack_stats.py`: the main method, "v1".
- `export_crack_stats_v3.py`: an alternative single-pass method, "v3".
- `export_crack_stats_v3_batch_bcd.py`: runs v3 on the thesis batches B, C and D.
- `add_definitions_sheet.py`: adds a column-definitions sheet to a v3 workbook.

**What it does.** For each micrograph, it runs pages 1–4 and turns the result into one row of
numbers: crack area, width, segment length and connectivity. The rows go into an `.xlsx`
spreadsheet. Every column is defined in
[`docs/batch_stats/crack_stats_schema.md`](../batch_stats/crack_stats_schema.md).

---

## `export_crack_stats.py` (v1)

### Settings and image selection, lines 41–112

| Line | Name | Meaning |
|---|---|---|
| 49 | `UM_PER_PX_MM_TAG` | 100/164 ≈ 0.61 µm per pixel. The calibration for the stitched "mm" mosaic images only, copied from an external calibration tool. All µm/mm² columns use it. |
| 56 | `KNOWN_BAD_FRAME_SUBSTRINGS` | Filenames that look like mosaics but aren't. Their µm columns are left empty. |
| 67 | `CONFIRMED_SCALE_BAR_IMAGES` | Images found by eye to have a burned-in blue scale bar. Always skipped. |
| 74 | `ADDITIONAL_IMAGES` | One extra image whose default capture is the wrong size, so a different index is used. |
| 77–78 | `RAW_GLOB`, `DEFAULT_DATA_DIR` | Pick every `*_mm000001.jpg` under `--data-dir` (default `data/raw`). |
| 83–84 | `SCALE_BAR_CHECKED` / `_NOT_CHECKED` | The two values the `scale_bar_check` column can take. |

**`find_batch_images(data_dir)`, line 87.** It collects the images:
1. Everything matching the pattern, plus the extra images that exist.
2. Minus the scale-bar images, printing a notice for each one skipped.
3. If nothing is left, it stops with a message telling you to pass `--data-dir`.

### Small helpers, lines 114–197

| Function | Line | What it computes |
|---|---|---|
| `median_pixelwise_width_px` | 114 | **Median crack width**: 2 × half-width at every skeleton pixel of every segment *not* next to a flaking cut, then the median. A direct per-pixel measurement. |
| `median_edge_length_px` | 136 | Median segment length, skipping segments next to the cut. Optionally restricted to one connected piece of the network (see below). |
| `giant_component_nodes` | 155 | Finds the **giant component**: the connected piece of the network with the most total crack length. Returns its node IDs. |
| `giant_component_span_px` | 174 | The straight-line distance between the two farthest-apart points of a set. It only checks points on the outer boundary (the convex hull), which is much faster and gives the same answer. |

A **connected component** is a piece of the network you can travel through without leaving the
cracks. A well-connected network has one giant component holding nearly all the length. A
fragmented one has many separate islands.

### `compute_row(image_path, ...)`, line 202: one image → one row

This is the heart of the export. Step by step:

| Lines | Step |
|---|---|
| 224 | `report = on_stage or (lambda _stage: None)`: if the GUI passed a progress callback, use it; otherwise do nothing. `report("...")` appears after each stage. |
| 225–228 | Load the image and binarize (page 1). |
| 235–240 | **Scout pass**: skeletonize (page 2), then find flakes (page 3). |
| 242–245 | If flakes were found, **skeletonize again** on the corrected mask. Otherwise reuse the scout result. |
| 247 | Build the graph (page 4). |
| 255–258 | Flag segments next to the flaking cut (page 3). |
| 262 | `crack_area_px2`: count of crack pixels in the cleaned mask. |
| 263–264 | Total length and number of segments, **excluding** cut-adjacent segments. |
| 266 | `avg_width_px = area / length`: a rough width. If a crack were a perfect strip, area ÷ length = width. |
| 267–269 | `avg_edge_length_px = length / number of segments`. |
| 274–276 | `median_width_px`: the direct per-pixel width, which reuses the width map the skeleton step already made. |
| 282–285 | Crack area as % of the area we actually have evidence about (image minus flakes). |
| 295–298 | Build the network as a `networkx` graph, **including** cut-adjacent segments. They're real connections, even if their lengths aren't trustworthy. |
| 299–308 | Number of separate pieces, and the giant component's share of total length. |
| 315–316 | Median segment length, overall and inside the giant component. |
| 326–334 | The giant component's span, measured over *every pixel* of its segments, not just its nodes. A closed loop with no junctions has only one node, but real physical size. |
| 336–347 | Convert to µm / mm² with the calibration, unless the file is a known bad frame. |
| 351–378 | Assemble the row: one dictionary entry per column. |
| 380–390 | If `cache_dir` was given, also save intermediate arrays and an overlay picture (page 12). |

**Two width numbers, on purpose.** `avg_width_px` (area ÷ length) and `median_width_px`
(per-pixel) are different estimates. Area ÷ length runs high where junction blobs add area
without adding length. The schema doc explains when to use which.

### Command-line part, lines 395–end

- **`add_batch_args`**: adds `--data-dir` and `--scale-bars-checked`. Every batch script shares
  these.
- **`main`**: finds images, runs `compute_row` on each, and writes the spreadsheet. The
  `scale_bar_check` column says "visually confirmed" only if you passed `--scale-bars-checked`.

```
python3 -m scripts.batch_stats.export_crack_stats --data-dir ../data/raw --scale-bars-checked
```

---

## `export_crack_stats_v3.py`: the single-pass alternative

v3 exists to cross-check v1 with a different way of handling flakes. Both are kept and both run.

| | v1 | v3 |
|---|---|---|
| Skeletonize | Twice (scout + corrected mask) | **Once**, on the uncorrected mask |
| Segments removed for flakes | Those passing *near* the cut (buffer) | Those with any pixel *inside* the flake |
| Removed from length/width stats | Yes | Yes |
| Removed from connectivity stats | **No** (kept as real connections) | **Yes**. Otherwise the flake's fake mesh would join separate networks |
| Crack area from | the re-cleaned corrected mask | `mask_corrected` (not re-cleaned) |
| Extra columns | none | `runtime_*` timings per stage |

**`compute_row`**, line 65, follows the same outline as v1. The differences are in the table
above. The comments explain why each v3 choice is needed. One example is why the giant
component total must also skip flake segments: in v3 they're still in the skeleton.

**v3 reuses v1's helpers** (median width, giant component, image finding, calibration) by
importing them.

## `export_crack_stats_v3_batch_bcd.py`

It runs v3 on three fixed lists of 19 thesis images:
- **B**: T5 PTFE, gap heights H50–H190.
- **C**: humidity series on membrane, with 75RH_NR212_v2 excluded at your request.
- **D**: T2/T3/T4 membrane, low gap height.

It adds a `batch` column. If any listed file is missing under `--data-dir`, it lists them all
and stops before doing any work.

## `add_definitions_sheet.py`

It adds a `definitions` sheet to a v3 workbook: one row per stats column, with a one-line
definition, unit and evidence tag. The text is condensed from the schema doc and adjusted where
v3 differs from v1.

---

## Worth knowing

- **Everything is computed on the full image**, not the corner crop that `analyze_image.py`
  uses by default.
- **Tests**: `tests/test_export_crack_stats.py` (13 tests) checks the helpers against shapes
  with known answers. `tests/test_export_crack_stats_v3.py` checks v3's flake rule. Nothing runs
  `compute_row` end to end on a real image (review finding 16).
- **Example outputs**: `examples/crack_stats_v1_full_dataset.xlsx` and friends are real runs.
