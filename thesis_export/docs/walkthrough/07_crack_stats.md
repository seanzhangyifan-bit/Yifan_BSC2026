# 7. Crack stats

**File**: `src/crackgraph/measures/crack_stats.py` (188 lines)

Computes the crack stats for one region of one engine result: area, width, segment length,
connectivity, flaking and pruning. Columns: [`crack_stats_schema.md`](../batch_stats/crack_stats_schema.md).

Whole image: exactly the old exporter's numbers (archived 2026-11-13). Other regions: page 6's
rules.

---

## Small helpers, lines 29–90

| Function | Line | What it computes |
|---|---|---|
| `crack_network_graph` | 29 | Network from the segment table: nodes, one connection per segment. A `MultiGraph`, so parallel segments between the same two junctions both count. |
| `giant_component_nodes` | 43 | The **giant component**: the connected piece with the most crack length. |
| `giant_component_span_px` | 56 | Distance between the two farthest points, checked on the convex hull only (same answer, faster). |
| `_length_inside_px` | 77 | Length of a segment inside the region: all of it, or the steps between neighbouring pixels both inside. |

A **connected component** is a piece you can travel through without leaving the cracks. Well
connected: one giant component holds nearly all the length. Fragmented: many islands.

## `measure_crack_stats(engine, region, settings)`, line 92

### Shared set-up, lines 93–108

| Lines | Step |
|---|---|
| 99 | `kept`: segments not touching a flake. Everything below uses only these. |
| 101–102 | `assigned`: kept segments whose middle pixel is in the region. |
| 104 | `crack_area_px2`: cleaned crack pixels in the region, minus flaked patches. |
| 105 | `excluded_px`: flaked pixels in the region. |
| 106–108 | `total_length_px`: crack length inside the region. |

### One block per column group

Each block runs only if its group is chosen. "In a region" says how a non-whole region counts
it; for the whole image every rule gives the plain total.

- **Pixels inside**: only pixels in the region count. Cells add up to the whole.
- **Middle pixel**: a segment or patch straddling a border goes to the one region holding its
  middle. Nothing is counted twice or lost.

Every `_px` column has a `_um` twin (`settings.um_per_px`).

**`area`, lines 111–119**

| Column | What it is | In a region |
|---|---|---|
| `crack_area_pct` | Crack pixels as % of the region's area. | Pixels inside. |
| `crack_area_pct_excl_flakes` | Crack pixels as % of the region's area minus its flaked pixels: the area we have evidence about. | Pixels inside. |
| `crack_area_mm2` | Crack area in mm². | Pixels inside. |

**`width`, lines 121–132**

| Column | What it is | In a region |
|---|---|---|
| `avg_width_px` | Crack area ÷ crack length. A rough width: for a perfect strip, area ÷ length = width. | Pixels inside, for both area and length. A segment crossing the border contributes only its length inside. |
| `median_width_px` | Median of 2 × half-width at every skeleton pixel. A direct per-pixel measurement. | Pixels inside. |

**`segment_length`, lines 134–141**

| Column | What it is | In a region |
|---|---|---|
| `avg_edge_length_px` | Mean segment length (junction or end to the next). | Middle pixel. Each segment keeps its full length, even the part outside the region. |
| `median_edge_length_px` | Median segment length. | Middle pixel, full length. |

**`connectivity`, lines 143–167**

| Column | What it is | In a region |
|---|---|---|
| `n_components` | Number of separate pieces of the crack network. | Not computed. Whole image only (see below). |
| `giant_component_fraction` | The largest piece's share of the total crack length. | Whole image only. |
| `median_edge_length_gc_px` | Median segment length inside the largest piece. | Whole image only. |
| `giant_component_span_px` | Straight-line distance between the largest piece's two farthest-apart pixels. | Whole image only. |

**`flaking`, lines 169–177**

| Column | What it counts | In a region |
|---|---|---|
| `flaking_excluded_area_pct` | Flaked **pixels**, as % of the region's area. | Pixels inside. |
| `flaking_n_candidates` | Flaked **patches**. | A patch counts where the centre of its bounding box lies. |
| `flaking_n_edges_omitted` | **Segments** left out of every measurement because they touch a flake. | Middle pixel. |

**`pruning`, lines 179–186**

| Column | What it counts | In a region |
|---|---|---|
| `n_host_stubs_pruned` | Short dead ends removed during skeletonizing because they barely leave the crack they branch from (page 2). | Middle pixel of the removed branch. |

**Notes**
- **Two widths.** `avg_width_px` (area ÷ length) runs high where junction blobs add area but no
  length; `median_width_px` is per pixel. The schema doc says when to use which.
- **Connectivity, whole image only (line 143).** Cutting at a border splits cracks, so a small
  cell would show many pieces even where the cracking is the same. Grid and centre runs put
  whole-image connectivity in the `image_connectivity` sheet (page 9).
- **Span over every pixel (lines 157–161).** A junction-free loop has one node but a real size.
- **Omitted segments are out of the network too.** A flake's own skeleton mesh would otherwise
  join separate networks.

## Tests

- `tests/test_crack_stats_measure.py`: helpers on known shapes, median width of a 10 px band, a
  border-crossing segment counted once.
- `tests/test_unified_analysis.py`: whole-image row vs the old exporter; 3×3 crack area adds up.
- `tests/test_flaking_omission.py`: the flake rule.

Example output: `examples/crack_stats_batch_bcd.xlsx` (thesis batches B, C, D; page 10).
