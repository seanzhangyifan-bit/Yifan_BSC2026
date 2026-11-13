"""Like run.py (current code), but with fragment removal switched off: the one
`is_fragment = ...` line in skeletonize_and_prune is patched at runtime so no
isolated piece is ever flagged. Spurs and host stubs are removed as normal.
Project code on disk is untouched. Run from thesis_export/: python3 <this> <out dir>"""
import inspect
import sys
import textwrap
from pathlib import Path

import pandas as pd

sys.path.insert(0, ".")
import src.crackgraph.skeleton as sk  # noqa: E402

code = textwrap.dedent(inspect.getsource(sk.skeletonize_and_prune))
old = 'is_fragment = (summary["branch_type"] == 0) & (summary["branch_distance"] < spur_px)'
assert code.count(old) == 1
exec(code.replace(old, 'is_fragment = summary["branch_type"] == -1  # never'), sk.__dict__)

import scripts.batch_stats.export_crack_stats as ex  # noqa: E402

ex.skeletonize_and_prune = sk.skeletonize_and_prune  # the exporter imported the name directly

RAW = Path("/home/seanzzz/UNI/crack-project/data/raw")
names = pd.read_excel("/home/seanzzz/UNI/crack-project/outputs/crack_stats_v2/thesis_stats.xlsx")
MAP = {"crack": "crack_area_pct_excl_flakes", "flaking": "flaking_excluded_area_pct", "wcrack": "median_width_um",
       "N": "n_components", "fgc": "giant_component_fraction", "ledge": "median_edge_length_um",
       "ledge_gc": "median_edge_length_gc_um", "dgc": "giant_component_span_um"}
out = Path(sys.argv[1]).resolve()
rows = []
for i, (fn, folder) in enumerate(zip(names.image_filename, names.source_folder), 1):
    print(f"[{i}/19] {fn}", flush=True)
    rows.append(ex.compute_row(RAW / folder / fn, scale_bar_check=ex.SCALE_BAR_NOT_CHECKED))
out.mkdir(parents=True, exist_ok=True)
df = pd.DataFrame(rows)
df.to_excel(out / "crack_stats.xlsx", index=False, sheet_name="crack_stats")
t = df[["image_filename", "source_folder"]].copy()
for k, v in MAP.items():
    t[k] = df[v]
t.to_excel(out / "thesis_stats.xlsx", index=False)
print("wrote", out)
