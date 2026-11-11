# 5. Crack-stats export

**Folder**: `scripts/batch_stats/`
- `export_crack_stats.py`: the export. Every micrograph → one row of numbers.
- `export_crack_stats_batch_bcd.py`: runs it on the thesis batches B, C and D. (can be ignored: same functionality as crack_stats_export, but with hardcoded filepaths as used during (Zhang 2026))
- `add_definitions_sheet.py`: adds a column-definitions sheet to a finished workbook.

**What it does.** For each micrograph, it runs pages 1–4 and turns the result into one row of
numbers: crack area, width, segment length and connectivity. The rows go into an `.xlsx`
spreadsheet. Every column is defined in
[`docs/batch_stats/crack_stats_schema.md`](../batch_stats/crack_stats_schema.md).

---

## `export_crack_stats.py`

### Settings and image selection, lines 43–77

| Line | Name | Meaning |
|---|---|---|
| 45 | `UM_PER_PX_MM_TAG` | 100/164 ≈ 0.61 µm per pixel. The calibration for the stitched "mm" mosaic images only, copied from an external calibration tool. All µm/mm² columns use it, for every image: nothing checks the magnification. |
| 50 | `IMAGE_SUFFIXES` | The file types picked up: `.jpg`, `.jpeg`, `.png`, `.tif`, `.tiff`, `.bmp`. |
| 51 | `DEFAULT_DATA_DIR` | Default for `--data-dir`: `data/raw`. |
| 56–57 | `SCALE_BAR_CHECKED` / `_NOT_CHECKED` | The two values the `scale_bar_check` column can take. |
| 62 | `COMPUTE_ROW_STAGES` | The stage names `compute_row` reports as it goes, for the GUI's progress bar. |

**`find_images(data_dir, pattern)`, line 65.** Every image file under the folder, in any
subfolder, sorted. It doesn't look at file names: which images get analysed is up to you, by what
you put in the folder (or upload in the GUI). If there are none, it stops with a message telling
you to pass `--data-dir`. `pattern` lets another script narrow it down; the junction cut-off sweep
uses it to pick its fixed image set.

### Small helpers, lines 79–164

| Function | Line | What it computes |
|---|---|---|
| `median_pixelwise_width_px` | 79 | **Median crack width**: 2 × half-width at every skeleton pixel of every segment *not* omitted for touching a flake, then the median. A direct per-pixel measurement. |
| `median_edge_length_px` | 99 | Median segment length, skipping omitted segments. Optionally restricted to one connected piece of the network (see below). |
| `crack_network_graph` | 116 | Builds the crack network from the segment table: junctions and ends as nodes, one connection per segment. A `MultiGraph`, so two different segments joining the same two junctions both count. |
| `giant_component_nodes` | 130 | Finds the **giant component**: the connected piece of the network with the most total crack length. Returns its node IDs. |
| `giant_component_span_px` | 145 | The straight-line distance between the two farthest-apart points of a set. It only checks points on the outer boundary (the convex hull), which is much faster and gives the same answer. |

A **connected component** is a piece of the network you can travel through without leaving the
cracks. A well-connected network has one giant component holding nearly all the length. A
fragmented one has many separate islands.

### `compute_row(image_path, ...)`, line 167: one image → one row

This is the heart of the export. Step by step:

| Lines | Step |
|---|---|
| 182 | `report = on_stage or (lambda _stage: None)`: if the GUI passed a progress callback, use it; otherwise do nothing. `report("...")` appears after each stage. |
| 184–188 | Load the image and binarize (page 1). |
| 196 | Skeletonize (page 2), **once**, flaked patches included. |
| 201–203 | Find flaked patches from that skeleton's width map (page 3). |
| 208 | Build the graph (page 4). |
| 214–216 | `omitted`: every segment with a pixel inside a flaked patch (page 3). These are left out of **everything** below. |
| 226 | `crack_area_px2`: crack pixels in the cleaned mask, minus the flaked patches. |
| 227–228 | Total length and number of segments, excluding omitted segments. |
| 230 | `avg_width_px = area / length`: a rough width. If a crack were a perfect strip, area ÷ length = width. |
| 231–233 | `avg_edge_length_px = length / number of segments`. |
| 235–237 | `median_width_px`: the direct per-pixel width, which reuses the width map the skeleton step already made. |
| 242–245 | Crack area as % of the area we actually have evidence about (image minus flakes). |
| 252–263 | Build the network from the **kept** segments only, then the number of separate pieces and the giant component's share of total length. Leaving omitted segments out matters: a flake's own skeleton is a branchy mesh that would otherwise connect separate crack networks. |
| 265–266 | Median segment length, overall and inside the giant component. |
| 272–284 | The giant component's span, measured over *every pixel* of its kept segments, not just its nodes. A closed loop with no junctions has only one node, but real physical size. |
| 286–294 | Convert to µm / mm² with the calibration, for every image. |
| 300–336 | Assemble the row: one dictionary entry per column, plus the time each stage took (`runtime_*`). |
| 338–348 | If `cache_dir` was given, also save intermediate arrays and an overlay picture (page 12). |

**Two width numbers, on purpose.** `avg_width_px` (area ÷ length) and `median_width_px`
(per-pixel) are different estimates. Area ÷ length runs high where junction blobs add area
without adding length. The schema doc explains when to use which.

### Command-line part, lines 353–end

- **`add_batch_args`**: adds `--data-dir` and `--scale-bars-checked`. Every batch script shares
  these.
- **`main`**: finds images, runs `compute_row` on each, and writes the spreadsheet. The
  `scale_bar_check` column says "visually confirmed" only if you passed `--scale-bars-checked`.

```
python3 -m scripts.batch_stats.export_crack_stats --data-dir ../data/raw --scale-bars-checked
```

---

## `export_crack_stats_batch_bcd.py`

It runs the same `compute_row` on three fixed lists of 19 thesis images:
- **B**: T5 PTFE, gap heights H50–H190.
- **C**: humidity series on membrane, with 75RH_NR212_v2 excluded at your request.
- **D**: T2/T3/T4 membrane, low gap height.

It adds a `batch` column. If any listed file is missing under `--data-dir`, it lists them all
and stops before doing any work.

## `add_definitions_sheet.py`

It adds a `definitions` sheet to a finished workbook: one row per stats column, with a one-line
definition, unit and evidence tag, condensed from the schema doc.

---

## Worth knowing

- **Everything is computed on the full image**, not the corner crop that `analyze_image.py`
  uses by default.
- **Tests**: `tests/test_export_crack_stats.py` (14 tests) checks the helpers against shapes
  with known answers. `tests/test_flaking_omission.py` checks the flake rule.
  `tests/test_entry_points.py` runs `compute_row` end to end on a small synthetic image with a
  flake.
- **Example output**: `examples/crack_stats_batch_bcd.xlsx` is a real run on batches B, C and D.
