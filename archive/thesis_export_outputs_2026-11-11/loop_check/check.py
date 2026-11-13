"""Check: are skeleton loops exactly the holes in the cleaned mask, across the dataset?

For every data/raw/**/*_mm000001.jpg (2048 px centre crop, real pipeline at
production defaults, no flaking exclusion):
- holes  = background components of mask_clean not touching the crop border
- loops  = independent cycles of the final crack graph (E - V + C)
- short_jj = junction-to-junction edges shorter than the image's average crack
  width (the skeleton_loop_sweep.py fingerprint), split into those within one
  crack width of a small hole (< width^2, a dark speck) and the rest.
Run from thesis_export/: python3 outputs/loop_check/check.py
"""
import sys
from pathlib import Path

import networkx as nx
import numpy as np
from scipy.ndimage import distance_transform_edt, label

sys.path.insert(0, ".")
from src.crackgraph.binarize import binarize  # noqa: E402
from src.crackgraph.graph import extract_graph  # noqa: E402
from src.crackgraph.io_utils import load_image  # noqa: E402
from src.crackgraph.skeleton import skeletonize_and_prune  # noqa: E402

CROP = 2048
rows = []
for path in sorted(Path("../data/raw").glob("**/*_mm000001.jpg")):
    g, _ = load_image(path)
    h, w = g.shape
    if min(h, w) < CROP:
        continue
    r0, c0 = (h - CROP) // 2, (w - CROP) // 2
    g = g[r0:r0 + CROP, c0:c0 + CROP]
    sr = skeletonize_and_prune(binarize(g).mask, source_image=g)
    s = extract_graph(sr.skeleton).summary
    if len(s) == 0:
        continue
    G = nx.MultiGraph()
    G.add_edges_from(zip(s.node_id_src, s.node_id_dst))
    loops = G.number_of_edges() - G.number_of_nodes() + nx.number_connected_components(G)

    m = sr.mask_clean
    lab, n = label(~m)
    border = set(np.unique(np.r_[lab[0], lab[-1], lab[:, 0], lab[:, -1]])) - {0}
    areas = np.bincount(lab.ravel())
    hole_ids = [i for i in range(1, n + 1) if i not in border]

    length = s.branch_distance.sum()
    avg_w = m.sum() / length
    small = np.isin(lab, [i for i in hole_ids if areas[i] < avg_w ** 2])
    d_small = distance_transform_edt(~small) if small.any() else np.full(m.shape, np.inf)

    jj = s[(s.branch_type == 2) & (s.branch_distance < avg_w)]
    near = 0
    for i in jj.index:
        c = np.round(sr.skeleton.path_coordinates(i)).astype(int)
        near += d_small[c[:, 0], c[:, 1]].min() <= avg_w
    rows.append((path.stem.replace("_mm000001", ""), len(hole_ids), loops, int(small.any() and
                 len([i for i in hole_ids if areas[i] < avg_w ** 2])), len(jj), int(near), len(s)))
    print(f"{rows[-1][0]:26s} holes {rows[-1][1]:4d} loops {loops:4d} | small holes {rows[-1][3]:3d} | "
          f"short jj {len(jj):3d} (near small hole {near:3d}) of {len(s)} edges", flush=True)

holes = np.array([r[1] for r in rows]); loops = np.array([r[2] for r in rows])
print(f"\n{len(rows)} images. holes == loops on {int((holes == loops).sum())}; "
      f"max |diff| {int(np.abs(holes - loops).max())}")
jj = sum(r[4] for r in rows); near = sum(r[5] for r in rows)
print(f"short jj edges: {jj} total, {near} near a small hole ({100 * near / max(jj, 1):.0f}%), "
      f"{jj - near} elsewhere ({100 * (jj - near) / max(jj, 1):.0f}%)")
