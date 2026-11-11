# 4. The crack network

**File**: `src/crackgraph/graph.py` (62 lines)

**What it does.** It turns the cleaned skeleton into a **graph**: points (junctions and loose
ends) connected by segments. Most of the work is done by the **skan** library. This file pulls
out what the rest of the project needs and counts junction types.

## skan's vocabulary

You'll see these names throughout the project. For a picture of nodes, endpoints and branch
types, see the skan figure in [02_skeleton.md](02_skeleton.md#what-the-library-steps-do).

| Term | Meaning |
|---|---|
| **node** | A junction or a loose end. Each has an ID (`node_id`). |
| **degree** | How many segments meet at a node. 1 = loose end, 2 = a plain bend (not a node), 3 = three-way junction, 4+ = crossing. |
| **path** / **branch** / **edge** | One segment of skeleton between two nodes. Numbered by `path_index`. |
| **summary table** | `skan.summarize(...)`: one row per segment. |
| `node_id_src`, `node_id_dst` | The segment's two end nodes ("source" and "destination", just labels, no direction implied). |
| `branch_distance` | The segment's length in pixels, following its pixels, not straight-line. |
| `branch_type` | 0 = isolated piece, 1 = dead end, 2 = junction to junction, 3 = closed loop. |
| `path_coordinates(i)` | The (row, col) of every pixel along segment `i`, in order from src to dst. |

## `GraphResult`, line 17

| Field | Meaning |
|---|---|
| `node_ids`, `node_coords`, `node_degree` | Every node: its ID, position, degree. |
| `n_endpoints` | Nodes with degree 1. `[measured]` |
| `n_junctions_deg3` | Three-way junctions. `[measured]` |
| `n_junctions_deg_ge4` | Crossings of 4 or more. `[measured]` |
| `n_edges` | Number of segments. |
| `summary` | The full skan summary table, kept for later steps. |

## `path_pixel_indices(coords, shape)`, line 28

A small shared helper. Skeleton coordinates can be fractional, so it rounds them to whole pixel
indices and clamps them inside the image, so a segment touching the border can't point off the
edge. It returns `(rows, cols)`, ready to look up values in any image-sized grid, such as the
width map. It's used by `skeleton.py`, `flaking.py` and the exporter.

## `extract_graph(skel)`, line 38

| Line | What happens |
|---|---|
| 39 | `summary = skan.summarize(skel, separator="_")`: the per-segment table. |
| 41–48 | Collect every node ID that appears at either end of any segment. `np.unique` removes duplicates. |
| 50–51 | Look up each node's degree and position in skan's skeleton. |
| 53–62 | Count degree-1, degree-3 and degree-≥4 nodes, and return everything. |

## Worth knowing

- **No T/Y here.** This step only knows *how many* segments meet at a node, not at what angles.
  Angles come in `junctions.py` (page 7).
- **Fake loops add fake junctions.** Each small thinning loop (page 2) creates two extra
  degree-3 nodes. That inflates junction counts, especially on wide-crack images.
- **Tests**: `tests/test_grid_synthetic.py` checks exact node and segment counts on synthetic
  grids and honeycombs whose topology is known exactly.
