# 4. The crack network

**File**: `src/crackgraph/graph.py` (60 lines)

Turns the skeleton into a **graph**: nodes (junctions, loose ends) joined by segments. skan does
most of the work; this file extracts what the project needs and counts nodes by degree.

## skan's vocabulary

Picture: the skan figure in [02_skeleton.md](02_skeleton.md#what-the-library-steps-do).

| Term | Meaning |
|---|---|
| **node** | A junction or loose end, with a `node_id`. |
| **degree** | Segments meeting at a node. 1 = loose end, 2 = plain bend (not a node), 3 = three-way junction, 4+ = crossing. |
| **path** / **branch** / **edge** | One segment between two nodes, numbered by `path_index`. |
| **summary table** | `skan.summarize(...)`: one row per segment. |
| `node_id_src`, `node_id_dst` | The segment's two end nodes (labels only, no direction). |
| `branch_distance` | Segment length in pixels, along the pixels. |
| `branch_type` | 0 = isolated piece, 1 = dead end, 2 = junction to junction, 3 = closed loop. |
| `path_coordinates(i)` | (row, col) of every pixel along segment `i`, src to dst. |

## `GraphResult`, line 15

| Field | Meaning |
|---|---|
| `node_ids`, `node_coords`, `node_degree` | Every node's ID, position, degree. |
| `n_endpoints` | Degree-1 nodes. `[measured]` |
| `n_junctions_deg3` | Three-way junctions. `[measured]` |
| `n_junctions_deg_ge4` | Crossings of 4+. `[measured]` |
| `n_edges` | Number of segments. |
| `summary` | The skan summary table. |

## `path_pixel_indices(coords, shape)`, line 26

Rounds a segment's coordinates to whole pixels, clamped inside the image. Returns `(rows, cols)`
for looking up values in any image-sized array (e.g. the width map). Used by `skeleton.py`,
`flaking.py` and `engine.py`.

## `extract_graph(skel)`, line 36

| Line | What happens |
|---|---|
| 37 | `skan.summarize(...)`: the per-segment table. |
| 39–46 | Collect every node ID at either end of a segment. |
| 48–49 | Look up each node's degree and position. |
| 51–60 | Count degree-1, degree-3 and degree-≥4 nodes; return. |

## Worth knowing

- **Counts only, no angles.**
- **Short segments add junctions.** A loop around a dark speck (page 2) adds two degree-3 nodes;
  a crossing read as two three-way junctions adds a short segment. Both inflate counts on
  wide-crack images.
- **Tests**: `tests/test_grid_synthetic.py` checks exact node and segment counts on synthetic
  grids and honeycombs.
