"""Run the real crack-stats exporter (compute_row) on the 19 thesis images and
write crack_stats.xlsx (all columns) + thesis_stats.xlsx (8 thesis columns).
Usage: python3 run.py <thesis_export code dir> <out dir>"""
import sys
from pathlib import Path

import pandas as pd

code, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
sys.path.insert(0, str(code))
from scripts.batch_stats.export_crack_stats import SCALE_BAR_NOT_CHECKED, compute_row  # noqa: E402

RAW = Path("/home/seanzzz/UNI/crack-project/data/raw")
names = pd.read_excel("/home/seanzzz/UNI/crack-project/outputs/crack_stats_v2/thesis_stats.xlsx")
MAP = {"crack": "crack_area_pct_excl_flakes", "flaking": "flaking_excluded_area_pct", "wcrack": "median_width_um",
       "N": "n_components", "fgc": "giant_component_fraction", "ledge": "median_edge_length_um",
       "ledge_gc": "median_edge_length_gc_um", "dgc": "giant_component_span_um"}
rows = []
for i, (fn, folder) in enumerate(zip(names.image_filename, names.source_folder), 1):
    print(f"[{i}/19] {fn}", flush=True)
    rows.append(compute_row(RAW / folder / fn, scale_bar_check=SCALE_BAR_NOT_CHECKED))
out.mkdir(parents=True, exist_ok=True)
df = pd.DataFrame(rows)
df.to_excel(out / "crack_stats.xlsx", index=False, sheet_name="crack_stats")
t = df[["image_filename", "source_folder"]].copy()
for k, v in MAP.items():
    t[k] = df[v]
t.to_excel(out / "thesis_stats.xlsx", index=False)
print("wrote", out)
