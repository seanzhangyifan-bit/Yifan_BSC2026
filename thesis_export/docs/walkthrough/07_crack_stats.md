# 7. Crack stats

**File**: `src/crackgraph/measures/crack_stats.py` (188 lines)

**What it does.** For one region of one engine result (page 5), it computes the crack stats:
crack area, width, segment length, connectivity, flaking and pruning counts. These are the
thesis's main numbers. Every column is defined in
[`docs/batch_stats/crack_stats_schema.md`](../batch_stats/crack_stats_schema.md).

For the whole image, the numbers are exactly those of the old crack-stats exporter
(`export_crack_stats.py`, archived 2026-11-13). For other regions, page 6's two rules apply:
pixels count where they are, and segments go whole to the region holding their middle pixel.

---

## Small helpers, lines 29–90

| Function | Line | What it computes |
|---|---|---|
| `crack_network_graph` | 29 | Builds the crack network from the segment table: junctions and ends as nodes, one connection per segment. A `MultiGraph`, so two different segments joining the same two junctions both count. |
| `giant_component_nodes` | 43 | Finds the **giant component**: the connected piece of the network with the most total crack length. Returns its node IDs. |
| `giant_component_span_px` | 56 | The straight-line distance between the two farthest-apart points of a set. It only checks points on the outer boundary (the convex hull), which is much faster and gives the same answer. |
| `_length_inside_px` | 77 | How much of one segment lies inside the region. The whole length if every pixel is inside; otherwise the sum of the steps between neighbouring pixels that are both inside. |

A **connected component** is a piece of the network you can travel through without leaving the
cracks. A well-connected network has one giant component holding nearly all the length. A
fragmented one has many separate islands.

## `measure_crack_stats(engine, region, settings)`, line 92

### Shared set-up, lines 93–108

| Lines | Step |
|---|---|
| 99 | `kept`: every segment not touching a flaked patch (page 3). Segments touching one are left out of **everything** below. |
| 101–102 | `assigned`: the kept segments whose middle pixel is in this region. |
| 104 | `crack_area_px2`: crack pixels inside the region, after cleaning and minus flaked patches. |
| 105 | `excluded_px`: flaked-patch pixels inside the region. |
| 106–108 | `total_length_px`: the length of crack inside the region, summed over every kept segment. |

### One block per column group

Each block runs only if you chose that group (`settings.crack_stats_groups`).

| Lines | Group | Columns |
|---|---|---|
| 111–119 | `area` | `crack_area_pct`: crack area as % of the region. `crack_area_pct_excl_flakes`: as % of the region minus flaked patches, the area we have evidence about. `crack_area_mm2`. |
| 121–132 | `width` | `avg_width_px` = crack area ÷ crack length, a rough width: for a perfect strip, area ÷ length = width. `median_width_px`: the median of 2 × half-width at every skeleton pixel inside the region, a direct per-pixel measurement. |
| 134–141 | `segment_length` | Mean and median length of the assigned segments, at full length. |
| 143–167 | `connectivity` | Whole image only (see below). Number of separate pieces, the giant component's share of the total length, its median segment length, and its span. |
| 169–177 | `flaking` | Flaked area as % of the region; flaked patches whose box centre is in the region; omitted segments whose middle pixel is in the region. |
| 179–186 | `pruning` | Host stubs removed (page 2) whose middle point is in the region. |

Every `_px` column has a `_um` twin, converted with `settings.um_per_px`.

**Two width numbers, on purpose.** `avg_width_px` (area ÷ length) and `median_width_px`
(per-pixel) are different estimates. Area ÷ length runs high where junction blobs add area
without adding length. The schema doc explains when to use which.

**Why connectivity is whole-image only (line 143).** Cutting the network at a region border
splits cracks that continue outside. A small grid cell would show many small separate pieces
even where the cracking is the same, so its connectivity would mostly measure the cell size.
When you choose a grid or the centre, the whole image's connectivity goes to its own
`image_connectivity` sheet instead (page 9).

**Why the span uses every pixel (lines 157–161).** A closed loop with no junctions has only one
node but a real physical size, so a span over nodes alone would be undefined.

---

## Worth knowing

- **Omitted segments are left out of the network too**, not just the lengths. A flake's own
  skeleton is a branchy mesh that would otherwise join separate crack networks.
- **Tests**:
  - `tests/test_crack_stats_measure.py`: the helpers against shapes with known answers, the
    median width of a 10 px band, and a segment crossing a cell border counted once.
  - `tests/test_unified_analysis.py`: the whole-image row against the old exporter's frozen
    output, and the crack area of a 3×3 grid adding up to the whole image.
  - `tests/test_flaking_omission.py`: the flake rule.
- **Example output**: `examples/crack_stats_batch_bcd.xlsx` is a run on thesis batches B, C
  and D (page 10).
